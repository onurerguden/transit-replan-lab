"""Compare real local coordination on fixed preference conflicts with identical offers."""

import asyncio
import hashlib
import os
from pathlib import Path
from time import perf_counter

from trl.agents import OllamaModel
from trl.contracts import CreateRun, Disrupt
from trl.disruptions import Overlay
from trl.domain import Architecture, Record
from trl.gtfs import load_schedule
from trl.orchestration import RunService
from trl.robustness import compare
from trl.routing import find_offers
from trl.scenarios import load_scenario
from trl.storage import RunStore
from trl.verify import verify_offer
from trl.vnext import Preference, preference_cost

from experiments.report import percentile
from experiments.vnext_runner import code_digest

ORIGINS = (
    ("metro:5", "tram:8"),
    ("metro:5", "tram:6"),
    ("metro:4", "tram:10"),
    ("metro:4", "tram:14"),
    ("metro:5", "tram:11"),
    ("metro:4", "tram:8"),
)
ARMS: tuple[tuple[str, Architecture, bool], ...] = (
    ("rules", "rules", False),
    ("single", "single", False),
    ("five", "five", True),
    ("five-no-counter", "five", False),
)
A: Preference = "earlier_arrival"
B: Preference = "less_wait"
OUTPUT = Path(".local/vnext-mediation")


class Measurement(Record):
    case: str
    arm: str
    pool_sha256: str
    status: str
    agreement: bool
    hard_violation: bool
    a_extra: int | None
    b_extra: int | None
    a_regret: int | None
    b_regret: int | None
    calls: int
    tokens: int
    ms: float


async def run() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    schedule = load_schedule()
    baseline = load_scenario()
    model = OllamaModel(os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    info = await model.info()
    store = RunStore(OUTPUT / "runs.sqlite")
    service = RunService(store, schedule, model)
    overlay = Overlay.compile((baseline.incident,))
    rows: list[Measurement] = []
    with (OUTPUT / "raw.jsonl").open("x", encoding="utf-8") as raw:
        for number, (a, b) in enumerate(ORIGINS, start=1):
            scenario = baseline.model_copy(
                update={
                    "id": f"preference-conflict-{number}",
                    "a": baseline.a.model_copy(update={"stop": a}),
                    "b": baseline.b.model_copy(update={"stop": b}),
                }
            )
            before = next(iter(find_offers(schedule, scenario, limit=1)), None)
            candidates = tuple(
                find_offers(
                    schedule, scenario, 1, overlay, diverse=True, initial=before
                )
            )
            offers, evidence = compare(
                schedule, scenario, candidates, overlay, before, "earliest"
            )
            if len(offers) < 2:
                continue
            best_a = min(preference_cost(offer, "a", A) for offer in offers)
            best_b = min(preference_cost(offer, "b", B) for offer in offers)
            if any(
                preference_cost(offer, "a", A) == best_a
                and preference_cost(offer, "b", B) == best_b
                for offer in offers
            ):
                continue
            expected = hashlib.sha256(
                "".join(offer.model_dump_json() for offer in offers).encode()
            ).hexdigest()
            for arm, architecture, counteroffers in ARMS:
                receipt = service.new_run(
                    CreateRun(
                        workflow="vnext",
                        architecture=architecture,
                        counteroffers=counteroffers,
                        preference_a=A,
                        preference_b=B,
                    ),
                    f"{scenario.id}:{arm}",
                    scenario,
                )
                queued = store.command(
                    receipt.run_id,
                    "incident",
                    Disrupt(version=0, notice=scenario.notice),
                )
                start = perf_counter()
                await service.execute(queued)
                elapsed = (perf_counter() - start) * 1000
                view = store.view(receipt.run_id)
                digest = hashlib.sha256(
                    "".join(offer.model_dump_json() for offer in view.offers).encode()
                ).hexdigest()
                if digest != expected:
                    raise ValueError(
                        "Coordination arms received different candidate pools."
                    )
                selected = next(
                    (offer for offer in view.offers if offer.id == view.verified_offer),
                    None,
                )
                row = next(
                    (
                        item
                        for item in evidence
                        if selected and item.offer_id == selected.id
                    ),
                    None,
                )
                invalid = bool(
                    selected
                    and verify_offer(
                        schedule,
                        scenario,
                        selected,
                        tuple(v for v in view.votes if v.offer_id == selected.id),
                        queued.version,
                        overlay,
                    )
                )
                measured = Measurement(
                    case=scenario.id,
                    arm=arm,
                    pool_sha256=digest,
                    status=view.status,
                    agreement=selected is not None and not invalid,
                    hard_violation=invalid,
                    a_extra=row.extra_seconds_a if row else None,
                    b_extra=row.extra_seconds_b if row else None,
                    a_regret=preference_cost(selected, "a", A) - best_a
                    if selected
                    else None,
                    b_regret=preference_cost(selected, "b", B) - best_b
                    if selected
                    else None,
                    calls=view.metrics.calls,
                    tokens=view.metrics.input_tokens + view.metrics.output_tokens,
                    ms=round(elapsed, 3),
                )
                rows.append(measured)
                raw.write(measured.model_dump_json() + "\n")
                raw.flush()
                os.fsync(raw.fileno())
                print(scenario.id, arm, view.status, view.metrics.calls, flush=True)
    if not rows:
        raise ValueError("The fixed fixtures do not expose any preference conflicts.")
    report = [
        "# vNext mediation evaluation",
        "",
        f"Model digest `{info.digest}`.",
        f"Source digest `{code_digest()}`.",
        "",
        "Rider A prefers earlier arrival. Rider B prefers less waiting at the meeting stop.",
        "Preference regret is measured in seconds above each rider’s best displayed option.",
        "",
        "| Arm | Agreement | A mean regret (s) | B mean regret (s) | Calls | p95 (s) | Hard violations |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, _, _ in ARMS:
        results = [item for item in rows if item.arm == arm]
        accepted = [item for item in results if item.agreement]
        a_regret = (
            sum(item.a_regret or 0 for item in accepted) / len(accepted)
            if accepted
            else 0
        )
        b_regret = (
            sum(item.b_regret or 0 for item in accepted) / len(accepted)
            if accepted
            else 0
        )
        report.append(
            f"| {arm} | {len(accepted)}/{len(results)} | {a_regret:.1f} | {b_regret:.1f} | "
            f"{sum(item.calls for item in results)} | {percentile([item.ms for item in results], 0.95) / 1000:.2f} "
            f"| {sum(item.hard_violation for item in results)} |"
        )
    (OUTPUT / "report.md").write_text("\n".join(report) + "\n")


if __name__ == "__main__":
    asyncio.run(run())
