"""Run fixed bilingual intake, question, and route comparisons on local Ollama."""

import argparse
import asyncio
import hashlib
import json
import os
import resource
import subprocess
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from random import Random
from time import perf_counter
from typing import Literal

from pydantic import TypeAdapter, ValidationError
from trl.agents import OllamaModel, RoleView
from trl.disruptions import Overlay
from trl.domain import Disruption, Offer, Record, Scenario
from trl.gtfs import Schedule, load_schedule
from trl.intake import Evaluate, answer_facts, decide, extract, slot_facts
from trl.notice import rule_notice
from trl.robustness import compare, snapshot_id
from trl.routing import SearchIncomplete, find_offers
from trl.scenarios import load_scenario
from trl.verify import check_plan
from trl.vnext import Extraction, Fact, Hypothesis, Intake

from experiments.report import percentile
from experiments.vnext_cases import ROOT, Case, audit, read

OUTPUT = Path(".local/vnext-results")
ARMS = ("legacy", "rules", "hybrid", "generic", "fixed", "adapter")


class Result(Record):
    case: str
    group: str
    language: str
    family: str
    arm: str
    initial: str
    terminal: str
    correct: bool
    auto_correct: bool
    unsupported: bool
    requested_fields: int
    model_calls: int
    model_ms: float
    elapsed_ms: float
    verified: bool
    hard_violation: bool
    confidence_band: int
    incident: Disruption | None
    meeting: int | None


class Context:
    def __init__(self, schedule: Schedule) -> None:
        self.schedule = schedule

    @lru_cache(maxsize=1024)  # noqa: B019 - bounded to this runner's lifetime
    def route(self, tight: bool, data: str) -> tuple[str, Offer | None]:
        scenario = load_scenario("infeasible" if tight else "demo")
        event = DisruptionAdapter.validate_json(data)
        overlay = Overlay.compile((event,))
        try:
            offers = find_offers(self.schedule, scenario, 1, overlay, limit=1)
        except SearchIncomplete:
            return "search_incomplete", None
        return ("verified", offers[0]) if offers else ("infeasible", None)

    def preview(self, tight: bool) -> Evaluate:
        def evaluate(
            incident: Disruption,
        ) -> tuple[
            Literal["feasible", "infeasible", "search_incomplete"], Offer | None
        ]:
            status, offer = self.route(tight, incident.model_dump_json())
            return (
                "feasible"
                if status == "verified"
                else "search_incomplete"
                if status == "search_incomplete"
                else "infeasible"
            ), offer

        return evaluate


DisruptionAdapter = TypeAdapter(Disruption)


def finish(
    case: Case,
    initial: str,
    final: Intake,
    context: Context,
    arm: str,
    fields: int,
    calls: int,
    model_ms: float,
    start: float,
    confidence: int,
) -> Result:
    scenario = load_scenario("infeasible" if case.tight_window else "demo")
    incident = final.selected.incident if final.selected else None
    status, offer = (
        context.route(case.tight_window, incident.model_dump_json())
        if incident is not None
        else (final.action, None)
    )
    expected = {
        "feasible": "verified",
        "infeasible": "infeasible",
        "abstained": "abstain",
    }[case.expected_plan_status]
    violation = bool(
        offer
        and (
            case.incident is None
            or check_plan(
                context.schedule, scenario, offer, Overlay.compile((case.incident,))
            )
            is not None
        )
    )
    supported = incident is None or incident == case.incident
    return Result(
        case=case.id,
        group=case.group,
        language=case.language,
        family=case.family,
        arm=arm,
        initial=initial,
        terminal=status,
        correct=initial == case.initial_action
        and status == expected
        and incident == case.incident
        and not violation,
        auto_correct=initial == "apply"
        and incident is not None
        and incident == case.incident
        and case.initial_action == "apply"
        and not violation,
        unsupported=not supported
        or (initial == "apply" and case.initial_action != "apply"),
        requested_fields=fields,
        model_calls=calls,
        model_ms=round(model_ms, 3),
        elapsed_ms=round((perf_counter() - start) * 1000, 3),
        verified=offer is not None,
        hard_violation=violation,
        confidence_band=confidence,
        incident=incident,
        meeting=offer.meeting if offer else None,
    )


async def measure(
    case: Case,
    arm: str,
    context: Context,
    model: OllamaModel | None,
) -> Result:
    start = perf_counter()
    schedule = context.schedule
    day = load_scenario().service_date
    preview = context.preview(case.tight_window)
    facts, reasons = extract(case.notice, schedule, day)
    calls, model_ms = 0, 0.0
    if model is not None and not slot_facts(facts, "kind") and not reasons:
        begin = perf_counter()
        calls = 1
        try:
            view: RoleView = {"notice": case.notice}
            response = await model.generate("operator_vnext", view, Extraction, False)
            facts, reasons = extract(
                case.notice,
                schedule,
                day,
                Extraction.model_validate_json(response.content),
            )
        except (ValidationError, ValueError):
            reasons = ("model_schema",)
        model_ms = (perf_counter() - begin) * 1000
    initial = decide(
        facts,
        reasons,
        schedule,
        day,
        preview,
        1,
        strategy="fixed" if arm == "fixed" else "impact",
    )
    if arm == "legacy":
        event = rule_notice(case.notice, schedule, day)
        action = "apply" if event else "ask"
        if event is None and case.answer and case.answer != "unknown":
            event = rule_notice(f"{case.notice}\n{case.answer}", schedule, day)
        final = (
            Intake(
                action="apply",
                facts=(),
                selected=Hypothesis(id="legacy", incident=event, facts=()),
            )
            if event
            else Intake(action="abstain", facts=())
        )
        return finish(
            case,
            action,
            final,
            context,
            arm,
            0 if action == "apply" else 3,
            0,
            0,
            start,
            2 if action == "apply" else 0,
        )
    final, fields = initial, 0
    if initial.question:
        fields = 3 if arm == "generic" else 1
        resolved: tuple[Fact, ...] = ()
        if case.answer and initial.question.slot == case.question_slot:
            resolved = answer_facts(initial, case.answer, None, schedule, day)
        final = decide(resolved, (), schedule, day, preview, 1, answered=True)
    return finish(
        case,
        initial.action,
        final,
        context,
        arm,
        fields,
        calls,
        model_ms,
        start,
        (1 if calls else 2) if initial.action == "apply" else 0,
    )


def paired_interval(
    baseline: list[Result], candidate: list[Result]
) -> tuple[float, float]:
    old = {item.case: item.correct for item in baseline}
    grouped: dict[str, list[int]] = defaultdict(list)
    for item in candidate:
        if item.case in old:
            grouped[item.group].append(int(item.correct) - int(old[item.case]))
    differences = [sum(group) / len(group) for group in grouped.values()]
    if not differences:
        return 0.0, 0.0
    rng = Random(42)
    draws = [
        100 * sum(rng.choices(differences, k=len(differences))) / len(differences)
        for _ in range(2000)
    ]
    return percentile(draws, 0.025), percentile(draws, 0.975)


def render(rows: list[Result]) -> str:
    lines = [
        "# vNext intake and clarification evaluation",
        "",
        (
            "| Arm | Correct outcome | Automatic paraphrase | TR correct | EN correct | "
            "Requested fields | Calls | p95 model (ms) | Unsupported | Hard violations | "
            "Difference vs v1 (95% grouped interval) |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    baseline = [row for row in rows if row.arm == "legacy"]
    for arm in ARMS:
        data = [row for row in rows if row.arm == arm]
        if not data:
            continue
        paraphrase = [row for row in data if row.family == "paraphrase"]
        tr = [row for row in data if row.language == "tr"]
        en = [row for row in data if row.language == "en"]
        lower, upper = paired_interval(baseline, data)
        p95 = percentile([row.model_ms for row in data if row.model_calls], 0.95)
        lines.append(
            f"| {arm} | {sum(row.correct for row in data)}/{len(data)} | "
            f"{sum(row.auto_correct for row in paraphrase)}/{len(paraphrase)} | "
            f"{sum(row.correct for row in tr)}/{len(tr)} | {sum(row.correct for row in en)}/{len(en)} | "
            f"{sum(row.requested_fields for row in data)} | {sum(row.model_calls for row in data)} | "
            f"{p95:.0f} | {sum(row.unsupported for row in data)} | "
            f"{sum(row.hard_violation for row in data)} | [{lower:+.1f}, {upper:+.1f}] pp |"
        )
    lines.extend(
        (
            "",
            "## Risk and coverage by evidence threshold",
            "",
            "| Arm | Minimum evidence band | Automatically processed | Wrong event |",
            "| --- | ---: | ---: | ---: |",
        )
    )
    for arm in ("rules", "hybrid", "adapter"):
        data = [row for row in rows if row.arm == arm]
        if data:
            for threshold in (1, 2):
                retained = [row for row in data if row.confidence_band >= threshold]
                lines.append(
                    f"| {arm} | {threshold} | {len(retained)}/{len(data)} | "
                    f"{sum(row.unsupported for row in retained)}/{len(retained)} |"
                )
    lines.extend(
        ("", "Band 2 is deterministic evidence. Band 1 adds a model-supplied quote.")
    )
    return "\n".join(lines) + "\n"


def profile(schedule: Schedule, scenario: Scenario) -> dict[str, object]:
    overlay = Overlay.compile((scenario.incident,))
    initial = find_offers(schedule, scenario, limit=1)[0]
    candidates = tuple(
        find_offers(schedule, scenario, 1, overlay, diverse=True, initial=initial)
    )
    stages: dict[str, object] = {}
    for reuse in (False, True):
        offers, evidence = compare(
            schedule,
            scenario,
            candidates,
            overlay,
            initial,
            "robust",
            reuse_equivalent=reuse,
        )
        elapsed: list[float] = []
        for _ in range(15):
            start = perf_counter()
            offers, evidence = compare(
                schedule,
                scenario,
                candidates,
                overlay,
                initial,
                "robust",
                reuse_equivalent=reuse,
            )
            elapsed.append((perf_counter() - start) * 1000)
        stages["shared_results" if reuse else "serial"] = {
            "p50_ms": percentile(elapsed, 0.5),
            "p95_ms": percentile(elapsed, 0.95),
            "evaluations_per_second": len(candidates)
            * 128
            * 1000
            / percentile(elapsed, 0.5),
            "peak_process_rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "offers": [item.model_dump() for item in evidence],
            "meetings": [item.meeting for item in offers],
        }
    return stages


def code_digest() -> str:
    digest = hashlib.sha256()
    paths = sorted(
        (
            *Path("backend/src/trl").rglob("*.py"),
            *Path("backend/src/trl/prompts").glob("*.md"),
            *Path("experiments").glob("vnext_*.py"),
        )
    )
    for path in paths:
        digest.update(
            str(path).encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest()
        )
    return digest.hexdigest()


async def run(
    split: str, arms: tuple[str, ...], directory: Path, adapter: str | None
) -> None:
    if split == "locked":
        audit(ROOT)
    cases = read(ROOT, split)
    schedule = load_schedule()
    endpoint = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    models = {
        arm: OllamaModel(endpoint, model=adapter)
        if arm == "adapter" and adapter
        else OllamaModel(endpoint)
        for arm in arms
        if arm in {"hybrid", "adapter"}
    }
    if "adapter" in arms and not adapter:
        raise ValueError("Provide the local adapter tag.")
    directory.mkdir(parents=True, exist_ok=True)
    condition = {
        "split": split,
        "arms": arms,
        "snapshot": snapshot_id(load_scenario()),
        "data": hashlib.sha256((ROOT / f"{split}.jsonl").read_bytes()).hexdigest(),
        "git": (
            await asyncio.to_thread(
                subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
            )
        ).strip(),
        "source": code_digest(),
        "models": {arm: (await model.info()).digest for arm, model in models.items()},
    }
    (directory / f"{split}-conditions.json").write_text(
        json.dumps(condition, indent=2) + "\n"
    )
    rows: list[Result] = []
    context = Context(schedule)
    with (directory / f"{split}.jsonl").open("x", encoding="utf-8") as handle:
        for arm in arms:
            for index, case in enumerate(cases, start=1):
                row = await measure(case, arm, context, models.get(arm))
                rows.append(row)
                handle.write(row.model_dump_json() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                if index % 10 == 0:
                    print(f"{split} {arm}: {index}/{len(cases)} cases", flush=True)
    (directory / f"{split}.md").write_text(render(rows), encoding="utf-8")
    if split == "dev":
        data = profile(schedule, load_scenario())
        (directory / "performance.json").write_text(json.dumps(data, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split", choices=("dev", "calibration", "locked"), required=True
    )
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=ARMS[:-1])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--adapter")
    args = parser.parse_args()
    asyncio.run(run(args.split, tuple(args.arms), args.output, args.adapter))


if __name__ == "__main__":
    main()
