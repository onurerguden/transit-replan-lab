"""Run the declared route slice with a local adapted Operator."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from trl.agents import OllamaModel
from trl.contracts import CreateRun, Disrupt
from trl.disruptions import Overlay
from trl.gtfs import load_schedule
from trl.orchestration import RunService
from trl.storage import RunStore
from trl.verify import verify_offer

from experiments.report import rows
from experiments.runner import cases


async def evaluate(output: Path, name: str) -> None:
    schedule = load_schedule()
    store = RunStore(output.with_suffix(".sqlite"))
    model = OllamaModel(
        os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), operator_model=name
    )
    service = RunService(store, schedule, model)
    locked = cases("locked")
    subset = [
        case
        for family in ("interchange", "platform")
        for case in [
            item for item in locked if item.family == family and item.ablation
        ][:2]
    ]
    baseline = {
        row.case: row
        for row in rows(Path("experiments/results/locked.jsonl"))
        if row.arm == "five"
    }
    digest = (await model.stage_info("operator")).digest
    results: list[dict[str, str | bool | int | None]] = []
    for case in subset:
        scenario = case.scenario
        run = service.new_run(CreateRun(architecture="five"), scenario.id, scenario)
        receipt = store.command(
            run.run_id, "notice", Disrupt(version=0, notice=scenario.notice)
        )
        await service.execute(receipt)
        body, view = store.read(run.run_id), store.view(run.run_id)
        offer = next(
            (item for item in view.offers if item.id == view.verified_offer), None
        )
        incident_correct = body.incident == scenario.incident
        violation = (
            offer is not None
            and verify_offer(
                schedule,
                scenario,
                offer,
                tuple(v for v in view.votes if v.offer_id == offer.id),
                view.version,
                Overlay.compile((scenario.incident,)),
            )
            is not None
        )
        result = {
            "case": scenario.id,
            "baseline_status": baseline[scenario.id].status,
            "baseline_correct": baseline[scenario.id].outcome_correct,
            "status": view.status,
            "incident_correct": incident_correct,
            "hard_violation": violation,
            "error": view.error,
            "calls": view.metrics.calls,
            "operator_digest": digest,
        }
        results.append(result)
        print(json.dumps(result), flush=True)
        output.write_text(json.dumps(results, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", required=True)
    parser.add_argument(
        "--output", type=Path, default=Path(".local/finetune/routes.json")
    )
    args = parser.parse_args()
    asyncio.run(evaluate(args.output, args.adapter))


if __name__ == "__main__":
    main()
