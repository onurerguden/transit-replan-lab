"""Run a checksum-locked comparison against one local Ollama instance."""

import argparse
import asyncio
import fcntl
import hashlib
import json
import os
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import uuid4

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
from .report import Row, report

ARMS: tuple[Architecture, ...] = ("rules", "single", "three", "five")


def cases(split: str) -> list[Case]:
    directory = DATA_ROOT / "scenarios"
    manifest = json.loads((directory / "manifest.json").read_text())
    data = (directory / split / "cases.jsonl").read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest[split]:
        raise SystemExit(f"{split} scenario checksum mismatch.")
    return [Case.model_validate_json(line) for line in data.splitlines()]


@dataclass(frozen=True)
class Condition:
    commit: str
    source_diff: str | None
    execution: Literal["replay", "ollama"]
    model_digest: str
    operator_digest: str | None
    gtfs: dict[str, str]

    def accepts(self, row: Row, split: str) -> bool:
        uses_model = row.arm != "rules"
        return (
            row.split == split
            and row.commit == self.commit
            and row.source_diff == self.source_diff
            and row.execution == self.execution
            and row.prompt_version == PROMPT_VERSION
            and row.seed == 42
            and row.gtfs == self.gtfs
            and row.model_digest == (self.model_digest if uses_model else "rules")
            and row.operator_digest == (self.operator_digest if uses_model else None)
        )


def revision(split: str) -> tuple[str, str | None]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"])
    if not dirty:
        return commit, None
    if split == "locked":
        raise SystemExit("Run the locked evaluation from a clean checkout.")
    sources = (
        "backend/src",
        "backend/pyproject.toml",
        "backend/uv.lock",
        "experiments/*.py",
        "data/scenarios/dev",
        "data/gtfs",
        "data/fixtures",
    )
    patch = subprocess.check_output(
        [
            "git",
            "diff",
            "--no-ext-diff",
            "--full-index",
            "--binary",
            "HEAD",
            "--",
            *sources,
        ]
    )
    digest = hashlib.sha256(patch)
    untracked = subprocess.check_output(
        ["git", "ls-files", "-z", "--others", "--exclude-standard", "--", *sources]
    )
    if not patch and not untracked:
        return commit, None
    for name in sorted(item for item in untracked.split(b"\0") if item):
        path = Path(os.fsdecode(name))
        content = (
            os.fsencode(os.readlink(path)) if path.is_symlink() else path.read_bytes()
        )
        digest.update(name + b"\0" + hashlib.sha256(content).digest())
    return commit, digest.hexdigest()


@contextmanager
def lock_results(path: Path) -> Generator[None]:
    with path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise SystemExit(
                "An evaluation is already writing to this output directory."
            ) from exc
        yield


def recover_rows(path: Path) -> list[Row]:
    if not path.is_file():
        return []
    with path.open("rb+") as handle:
        payload = handle.read()
        end = payload.rfind(b"\n") + 1
        completed = [
            Row.model_validate_json(line) for line in payload[:end].splitlines()
        ]
        if len({(row.case, row.arm) for row in completed}) != len(completed):
            raise SystemExit("Results contain duplicate case and coordinator pairs.")
        if end != len(payload):
            handle.truncate(end)
            os.fsync(handle.fileno())
    return completed


async def evaluate(split: str, output: Path, replay: bool, limit: int | None) -> None:
    if limit is not None and (not replay or limit <= 0):
        raise SystemExit("Provide a positive limit only for replay smoke tests.")
    if replay and split != "dev":
        raise SystemExit("Replay smoke tests use the development split.")
    output.mkdir(parents=True, exist_ok=True)
    with lock_results(output / f"{split}.lock"):
        await run_cases(split, output, replay, limit)


async def run_cases(split: str, output: Path, replay: bool, limit: int | None) -> None:
    result_path = output / f"{split}.jsonl"
    commit, source_diff = revision(split)
    data = recover_rows(result_path)
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
    operator_digest = None
    if isinstance(model, OllamaModel) and model.operator_model:
        operator_digest = (await model.stage_info("operator")).digest
    service = RunService(store, schedule, model)
    condition = Condition(
        commit=commit,
        source_diff=source_diff,
        execution="replay" if replay else "ollama",
        model_digest=info.digest,
        operator_digest=operator_digest,
        gtfs={
            item.id: item.sha256
            for item in feed_specs(DATA_ROOT / "gtfs")
            if "core" in item.profiles and item.sha256
        },
    )
    if any(not condition.accepts(row, split) for row in data):
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
                    # Only a durable result row counts as a completed measurement.
                    f"{scenario.id}:{arm}:{uuid4().hex}",
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
                    model_digest=condition.model_digest
                    if architecture != "rules"
                    else "rules",
                    operator_digest=condition.operator_digest
                    if architecture != "rules"
                    else None,
                    execution=condition.execution,
                    gtfs=condition.gtfs,
                    source_diff=condition.source_diff,
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
                done.add((scenario.id, arm))
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
    if args.replay and args.split != "dev":
        parser.error("--replay requires --split dev")

    async def exercise() -> None:
        splits = ("dev", "locked") if args.split == "all" else (args.split,)
        for split in splits:
            await evaluate(split, args.output, args.replay, args.limit)

    asyncio.run(exercise())


if __name__ == "__main__":
    main()
