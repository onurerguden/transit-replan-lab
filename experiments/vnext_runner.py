"""Run fixed bilingual intake, question, and route comparisons on local Ollama."""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import resource
import subprocess
import sys
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from random import Random
from time import perf_counter
from typing import Literal

import httpx
from ollama import ResponseError
from pydantic import TypeAdapter, ValidationError
from trl.agents import PROMPT_DIR, ModelError, OllamaModel, RoleView, view_digest
from trl.disruptions import Overlay
from trl.domain import Disruption, Offer, Record, Scenario
from trl.gtfs import Schedule, load_schedule
from trl.intake import (
    Evaluate,
    answer_facts,
    decide,
    extract,
    lexicon_proposal,
    slot_facts,
)
from trl.notice import rule_notice
from trl.robustness import compare, snapshot_id
from trl.routing import SearchIncomplete, find_offers
from trl.scenarios import load_scenario
from trl.verify import check_plan
from trl.vnext import Extraction, Fact, Hypothesis, Intake

from experiments.report import percentile
from experiments.runner import lock_results
from experiments.vnext_cases import ROOT, Case, audit, read

OUTPUT = Path(".local/vnext-results")
ARMS = ("legacy", "rules", "lexicon", "hybrid", "generic", "fixed", "adapter")


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
    model_response: str | None = None
    model_error: Literal["schema", "transport", "response"] | None = None
    request_sha256: str | None = None
    model_digest: str | None = None


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
    if arm == "lexicon":
        facts, reasons = extract(
            case.notice, schedule, day, lexicon_proposal(case.notice)
        )
    calls, model_ms = 0, 0.0
    raw_response = request_sha256 = model_digest = None
    model_error: Literal["schema", "transport", "response"] | None = None
    if model is not None and not slot_facts(facts, "kind") and not reasons:
        model_digest = (await model.info()).digest
        begin = perf_counter()
        calls = 1
        try:
            view: RoleView = {"notice": case.notice}
            request_sha256 = view_digest("operator_vnext", view)
            response = await model.generate("operator_vnext", view, Extraction, False)
            raw_response = response.content
            facts, reasons = extract(
                case.notice,
                schedule,
                day,
                Extraction.model_validate_json(response.content),
            )
        except (ValidationError, ValueError):
            model_error = "schema"
        except (httpx.HTTPError, ResponseError, ConnectionError):
            model_error = "transport"
        except ModelError:
            model_error = "response"
        if model_error:
            reasons = (f"model_{model_error}",)
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
    result = finish(
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
    return result.model_copy(
        update={
            "model_response": raw_response,
            "model_error": model_error,
            "correct": result.correct and model_error is None,
            "request_sha256": request_sha256,
            "model_digest": model_digest,
        }
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
            "Requested fields | Calls | p50 / p95 elapsed (ms) | p95 model (ms) | Unsupported | Hard violations | "
            "Difference vs v1 (95% grouped interval) |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    baseline_arm = "legacy" if any(row.arm == "legacy" for row in rows) else "rules"
    baseline = [row for row in rows if row.arm == baseline_arm]
    lines[2] = lines[2].replace("vs v1", f"vs {baseline_arm}")
    for arm in ARMS:
        data = [row for row in rows if row.arm == arm]
        if not data:
            continue
        paraphrase = [row for row in data if row.family == "paraphrase"]
        tr = [row for row in data if row.language == "tr"]
        en = [row for row in data if row.language == "en"]
        lower, upper = paired_interval(baseline, data)
        p95 = percentile([row.model_ms for row in data if row.model_calls], 0.95)
        elapsed = [row.elapsed_ms for row in data]
        interval = f"[{lower:+.1f}, {upper:+.1f}] pp" if baseline else "—"
        lines.append(
            f"| {arm} | {sum(row.correct for row in data)}/{len(data)} | "
            f"{sum(row.auto_correct for row in paraphrase)}/{len(paraphrase)} | "
            f"{sum(row.correct for row in tr)}/{len(tr)} | {sum(row.correct for row in en)}/{len(en)} | "
            f"{sum(row.requested_fields for row in data)} | {sum(row.model_calls for row in data)} | "
            f"{percentile(elapsed, 0.5):.1f} / {percentile(elapsed, 0.95):.1f} | "
            f"{p95:.0f} | {sum(row.unsupported for row in data)} | "
            f"{sum(row.hard_violation for row in data)} | {interval} |"
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
    for arm in ("rules", "lexicon", "hybrid", "adapter"):
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
            "offers": [item.model_dump() for item in evidence],
            "meetings": [item.meeting for item in offers],
        }
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        **stages,
        "peak_process_rss_bytes": peak * (1 if sys.platform == "darwin" else 1024),
    }


def code_digest() -> str:
    digest = hashlib.sha256()
    paths = sorted(
        (
            *Path("backend/src/trl").rglob("*.py"),
            *Path("backend/src/trl/prompts").glob("*.md"),
            *Path("experiments").glob("vnext_*.py"),
            Path("experiments/report.py"),
            Path("experiments/runner.py"),
            Path("backend/uv.lock"),
        )
    )
    for path in paths:
        digest.update(
            str(path).encode() + b"\0" + hashlib.sha256(path.read_bytes()).digest()
        )
    return digest.hexdigest()


def check_fresh_output(directory: Path, split: str) -> None:
    names = [
        f"{split}.jsonl",
        f"{split}-conditions.json",
        f"{split}.md",
        f"{split}-manifest.json",
    ]
    if split == "dev":
        names.append("performance.json")
    for name in names:
        if (directory / name).exists():
            raise FileExistsError(
                f"Refusing to overwrite experiment evidence: {directory / name}"
            )


async def run(
    split: str,
    arms: tuple[str, ...],
    directory: Path,
    adapter: str | None,
    *,
    exploratory: bool = False,
    benchmark: Path = ROOT,
) -> None:
    if not arms or len(set(arms)) != len(arms) or any(arm not in ARMS for arm in arms):
        raise ValueError("Provide distinct supported arms.")
    directory.mkdir(parents=True, exist_ok=True)
    with lock_results(directory / ".evaluation.lock"):
        check_fresh_output(directory, split)
        await run_fresh(
            split,
            arms,
            directory,
            adapter,
            exploratory=exploratory,
            benchmark=benchmark,
        )


async def run_fresh(
    split: str,
    arms: tuple[str, ...],
    directory: Path,
    adapter: str | None,
    *,
    exploratory: bool,
    benchmark: Path,
) -> None:
    if split == "locked" and not exploratory:
        raise ValueError(
            "The published locked set is already inspected. Use --exploratory or reproduce at v1.1.0."
        )
    if split == "locked":
        audit(benchmark)
    cases = read(benchmark, split)
    schedule = load_schedule()
    endpoint = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    models = {
        arm: OllamaModel(endpoint, model=adapter)
        if arm == "adapter" and adapter
        else OllamaModel(
            endpoint, model=os.environ.get("TRL_OLLAMA_MODEL", "qwen3.5:4b-q4_K_M")
        )
        for arm in arms
        if arm in {"hybrid", "adapter"}
    }
    if "adapter" in arms and not adapter:
        raise ValueError("Provide the local adapter tag.")
    runtime_version = None
    if models:
        async with httpx.AsyncClient(
            base_url=endpoint, timeout=10, trust_env=False
        ) as http:
            response = await http.get("/api/version")
            response.raise_for_status()
            runtime_version = str(response.json()["version"])
    condition = {
        "format_version": 2,
        "argv": ["python", "-m", "experiments.vnext_runner", *sys.argv[1:]],
        "system": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "ollama_version": runtime_version,
        "dirty_source_tree": bool(
            await asyncio.to_thread(
                subprocess.check_output, ["git", "status", "--porcelain"]
            )
        ),
        "operator_prompt_sha256": hashlib.sha256(
            (PROMPT_DIR / "operator_vnext.md").read_bytes()
        ).hexdigest(),
        "extraction_schema_sha256": hashlib.sha256(
            json.dumps(Extraction.model_json_schema(), sort_keys=True).encode()
        ).hexdigest(),
        "split": split,
        "arms": arms,
        "snapshot": snapshot_id(load_scenario()),
        "data": hashlib.sha256((benchmark / f"{split}.jsonl").read_bytes()).hexdigest(),
        "git": (
            await asyncio.to_thread(
                subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
            )
        ).strip(),
        "source": code_digest(),
        "evaluation": "exploratory"
        if exploratory or split == "locked"
        else "synthetic_holdout"
        if split == "holdout"
        else "development",
        "runtime": "Ollama constrained JSON; temperature=0; seed=42; num_ctx=4096; num_predict=260",
        "latency_scope": "seeded arm order; isolated route caches; warm local model; excludes API overhead",
        "models": {arm: (await model.info()).digest for arm, model in models.items()},
        "model_tags": {arm: model.model for arm, model in models.items()},
    }
    rows: list[Result] = []
    order = list(arms)
    Random(42).shuffle(order)
    condition["arm_order"] = order
    with (directory / f"{split}.jsonl").open("x", encoding="utf-8") as handle:
        with (directory / f"{split}-conditions.json").open(
            "x", encoding="utf-8"
        ) as metadata:
            metadata.write(json.dumps(condition, indent=2) + "\n")
        for arm in order:
            context = Context(schedule)
            for index, case in enumerate(cases, start=1):
                row = await measure(case, arm, context, models.get(arm))
                rows.append(row)
                handle.write(row.model_dump_json() + "\n")
                handle.flush()
                os.fsync(handle.fileno())
                if index % 10 == 0:
                    print(f"{split} {arm}: {index}/{len(cases)} cases", flush=True)
    report = directory / f"{split}.md"
    with report.open("x", encoding="utf-8") as handle:
        handle.write(render(rows))
    artifacts = [
        report,
        directory / f"{split}.jsonl",
        directory / f"{split}-conditions.json",
    ]
    if split == "dev":
        data = profile(schedule, load_scenario())
        performance = directory / "performance.json"
        with performance.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(data, indent=2) + "\n")
        artifacts.append(performance)
    with (directory / f"{split}-manifest.json").open("x", encoding="utf-8") as handle:
        hashes = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in artifacts
        }
        handle.write(
            json.dumps({"cases": len(cases), "sha256": hashes}, indent=2) + "\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split", choices=("dev", "calibration", "locked", "holdout"), required=True
    )
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=ARMS[:-1])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--adapter")
    parser.add_argument("--benchmark", type=Path, default=ROOT)
    parser.add_argument(
        "--exploratory",
        action="store_true",
        help="Explicitly label post-lock diagnostic evaluation",
    )
    args = parser.parse_args()
    asyncio.run(
        run(
            args.split,
            tuple(args.arms),
            args.output,
            args.adapter,
            exploratory=args.exploratory,
            benchmark=args.benchmark,
        )
    )


if __name__ == "__main__":
    main()
