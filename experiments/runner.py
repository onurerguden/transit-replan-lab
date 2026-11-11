"""Run a checksum-locked comparison against one local Ollama instance."""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Literal

from trl.agents import PROMPT_VERSION, OllamaModel, ReplayModel
from trl.contracts import CreateRun, Disrupt
from trl.disruptions import Overlay
from trl.domain import Architecture
from trl.gtfs import DATA_ROOT, feed_specs, load_schedule
from trl.orchestration import RunService
from trl.routing import find_offers
from trl.storage import RunStore
from trl.verify import verify_offer

from .generate import Case
from .report import Row, report, rows

ARMS: tuple[Architecture, ...] = ("rules", "single", "three", "five")


def cases(split: str) -> list[Case]:
    directory = DATA_ROOT / "scenarios"
    manifest = json.loads((directory / "manifest.json").read_text())
    data = (directory / split / "cases.jsonl").read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest[split]:
        raise SystemExit(f"{split} scenario checksum mismatch.")
    return [Case.model_validate_json(line) for line in data.splitlines()]


async def evaluate(split: str, output: Path, replay: bool, limit: int | None) -> None:
    if limit is not None and not replay:
        raise SystemExit("A limit is available only for replay smoke tests.")
    output.mkdir(parents=True, exist_ok=True)
    result_path = output / f"{split}.jsonl"
    data = rows(result_path) if result_path.is_file() else []
    done = {(row.case, row.arm) for row in data}
    schedule = load_schedule()
    store = RunStore(output / f"{split}.sqlite")
    model = (
        ReplayModel(schedule)
        if replay
        else OllamaModel(
            os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            operator_model=os.environ.get("TRL_OPERATOR_MODEL"),
        )
    )
    info = await model.info()
    digest = info.digest
    if isinstance(model, OllamaModel) and model.operator_model:
        digest = (await model.stage_info("operator")).digest
    service = RunService(store, schedule, model)
    revision = await asyncio.to_thread(
        subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
    )
    commit = revision.strip()
    feeds = {item.id: item.sha256 for item in feed_specs(DATA_ROOT / "gtfs")}
    if any(
        row.commit != commit
        or row.prompt_version != PROMPT_VERSION
        or row.gtfs != feeds
        or (row.arm != "rules" and row.model_digest != digest)
        for row in data
    ):
        raise SystemExit("Existing rows belong to a different experimental condition.")
    test_cases = cases(split)
    if limit is not None:
        test_cases = test_cases[:limit]
    with result_path.open("a", encoding="utf-8") as handle:
        for case in test_cases:
            scenario = case.scenario
            arms: list[tuple[Architecture, bool, str]] = [
                (arm, True, arm) for arm in ARMS
            ]
            if case.ablation:
                arms.append(("five", False, "five-no-counter"))
            if all((scenario.id, arm) in done for _, _, arm in arms):
                continue
            initial = find_offers(schedule, scenario, limit=1)
            truth = Overlay.compile((scenario.incident,))
            feasible = (
                []
                if case.ambiguous
                else find_offers(schedule, scenario, 1, truth, limit=1)
            )
            oracle: Literal["feasible", "infeasible", "clarification"] = (
                "clarification"
                if case.ambiguous
                else "feasible"
                if feasible
                else "infeasible"
            )
            for architecture, counteroffers, arm in arms:
                if (scenario.id, arm) in done:
                    continue
                request = CreateRun(
                    architecture=architecture, counteroffers=counteroffers
                )
                receipt = store.create(
                    request,
                    f"{scenario.id}:{arm}",
                    scenario,
                    initial[0] if initial else None,
                )
                work = store.command(
                    receipt.run_id,
                    "notice",
                    Disrupt(
                        version=0,
                        notice=scenario.notice,
                    ),
                )
                started = perf_counter()
                await service.execute(work)
                elapsed = round((perf_counter() - started) * 1000)
                run = store.read(receipt.run_id)
                view = store.view(receipt.run_id)
                selected = next(
                    (offer for offer in view.offers if offer.id == view.verified_offer),
                    None,
                )
                incident_correct = (
                    run.incident is None and run.status == "clarification"
                    if case.ambiguous
                    else run.incident == scenario.incident
                )
                hard_violation = False
                if selected is not None:
                    votes = tuple(
                        vote for vote in view.votes if vote.offer_id == selected.id
                    )
                    hard_violation = (
                        verify_offer(schedule, scenario, selected, votes, 1, truth)
                        is not None
                    )
                success = bool(
                    incident_correct and selected and not hard_violation and feasible
                )
                outcome_correct = success or (
                    incident_correct
                    and (
                        (oracle == "clarification" and run.status == "clarification")
                        or (oracle == "infeasible" and run.status == "infeasible")
                    )
                )
                row = Row(
                    split=split,
                    case=scenario.id,
                    family=case.family,
                    language=case.language,
                    arm=arm,
                    status=run.status,
                    oracle=oracle,
                    incident_correct=incident_correct,
                    outcome_correct=outcome_correct,
                    success=success,
                    hard_violation=hard_violation,
                    late_s=selected.meeting - feasible[0].meeting
                    if selected and feasible
                    else None,
                    delay_s=selected.meeting - initial[0].meeting
                    if selected and initial
                    else None,
                    calls=view.metrics.calls,
                    input_tokens=view.metrics.input_tokens,
                    output_tokens=view.metrics.output_tokens,
                    elapsed_ms=elapsed,
                    model_digest=digest if architecture != "rules" else "rules",
                    gtfs=feeds,
                    prompt_version=PROMPT_VERSION,
                    commit=commit,
                    seed=42,
                    counteroffers=counteroffers,
                    error=view.error,
                )
                handle.write(row.model_dump_json() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                data.append(row)
                print(
                    f"{split} {len(data)} {scenario.id} {arm} {run.status}", flush=True
                )
    (output / f"{split}.md").write_text(report(data), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("dev", "locked", "all"), default="all")
    parser.add_argument("--output", type=Path, default=Path(".local/experiment"))
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    async def exercise() -> None:
        splits = ("dev", "locked") if args.split == "all" else (args.split,)
        for split in splits:
            await evaluate(split, args.output, args.replay, args.limit)

    asyncio.run(exercise())


if __name__ == "__main__":
    main()
