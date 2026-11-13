"""Compare real local coordination on fixed preference conflicts with identical offers."""

import argparse
import asyncio
import hashlib
import os
from pathlib import Path
from time import perf_counter

from trl.agents import MODEL, OllamaModel
from trl.contracts import CreateRun, Disrupt
from trl.disruptions import Overlay
from trl.domain import Architecture, Offer, Record
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
PREFERENCES: tuple[tuple[Preference, Preference], ...] = (
    ("earlier_arrival", "less_wait"),
    ("fewer_transfers", "earlier_arrival"),
)
OUTPUT = Path(".local/vnext-mediation")


class Measurement(Record):
    case: str
    arm: str
    preference_a: Preference
    preference_b: Preference
    pool_sha256: str
    status: str
    agreement: bool
    hard_violation: bool
    a_extra: int | None
    b_extra: int | None
    a_regret: int | None
    b_regret: int | None
    worst_rank_regret: int | None
    calls: int
    tokens: int
    ms: float


async def run(output: Path, expanded: bool) -> None:
    output.mkdir(parents=True)
    schedule = load_schedule()
    baseline = load_scenario()
    model = OllamaModel(
        os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        model=os.environ.get("TRL_OLLAMA_MODEL", MODEL),
    )
    info = await model.info()
    store = RunStore(output / "runs.sqlite")
    service = RunService(store, schedule, model)
    overlay = Overlay.compile((baseline.incident,))
    rows: list[Measurement] = []
    with (output / "raw.jsonl").open("x", encoding="utf-8") as raw:
        scenarios = [(a, b, baseline.destinations, PREFERENCES[0]) for a, b in ORIGINS]
        if expanded:
            scenarios.append(
                ("metro:3", "tram:8", ("tram:3", "tram:10"), PREFERENCES[1])
            )
        for number, (a, b, destinations, preferences) in enumerate(scenarios, start=1):
            scenario = baseline.model_copy(
                update={
                    "id": f"preference-conflict-{number}",
                    "a": baseline.a.model_copy(update={"stop": a}),
                    "b": baseline.b.model_copy(update={"stop": b}),
                    "destinations": destinations,
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
            if not has_conflict(offers, *preferences):
                continue
            pa, pb = preferences
            costs_a = sorted({preference_cost(offer, "a", pa) for offer in offers})
            costs_b = sorted({preference_cost(offer, "b", pb) for offer in offers})
            expected = hashlib.sha256(
                "".join(offer.model_dump_json() for offer in offers).encode()
            ).hexdigest()
            for arm, architecture, counteroffers in ARMS:
                receipt = service.new_run(
                    CreateRun(
                        workflow="vnext",
                        architecture=architecture,
                        counteroffers=counteroffers,
                        preference_a=pa,
                        preference_b=pb,
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
                    preference_a=pa,
                    preference_b=pb,
                    pool_sha256=digest,
                    status=view.status,
                    agreement=selected is not None and not invalid,
                    hard_violation=invalid,
                    a_extra=row.extra_seconds_a if row else None,
                    b_extra=row.extra_seconds_b if row else None,
                    a_regret=preference_cost(selected, "a", pa) - costs_a[0]
                    if selected
                    else None,
                    b_regret=preference_cost(selected, "b", pb) - costs_b[0]
                    if selected
                    else None,
                    worst_rank_regret=max(
                        costs_a.index(preference_cost(selected, "a", pa)),
                        costs_b.index(preference_cost(selected, "b", pb)),
                    )
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
        "Preference pairs and raw regret appear in JSONL. Raw units follow each preference.",
        "Rank regret counts distinct cost levels above each rider’s best displayed option.",
        "",
        "| Arm | Agreement | Mean worst rider rank regret | Calls | p95 (s) | Hard violations |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm, _, _ in ARMS:
        results = [item for item in rows if item.arm == arm]
        accepted = [item for item in results if item.agreement]
        regret = (
            f"{sum(item.worst_rank_regret or 0 for item in accepted) / len(accepted):.2f}"
            if accepted
            else "—"
        )
        report.append(
            f"| {arm} | {len(accepted)}/{len(results)} | {regret} | "
            f"{sum(item.calls for item in results)} | {percentile([item.ms for item in results], 0.95) / 1000:.2f} "
            f"| {sum(item.hard_violation for item in results)} |"
        )
    (output / "report.md").write_text("\n".join(report) + "\n")


def has_conflict(offers: tuple[Offer, ...], pa: Preference, pb: Preference) -> bool:
    costs = [
        (preference_cost(offer, "a", pa), preference_cost(offer, "b", pb))
        for offer in offers
    ]
    return (min(a for a, _ in costs), min(b for _, b in costs)) not in costs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--expanded", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args.output, args.expanded))
