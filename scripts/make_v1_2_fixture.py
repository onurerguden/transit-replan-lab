"""Create the v1.2.0 upgrade fixture by running the v1.2.0 application code.

Usage (from the repository root):
    git worktree add --detach /tmp/trl-v120 v1.2.0
    uv sync --locked --project /tmp/trl-v120/backend
    PYTHONPATH=/tmp/trl-v120/backend/src TRL_DATA=/tmp/trl-v120/data \
      uv run --locked --project /tmp/trl-v120/backend python scripts/make_v1_2_fixture.py

The script writes a SQL dump and the views, events and receipts the old code produced.
"""

import asyncio
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

from trl.contracts import Clarify, CreateRun, Disrupt, EventDraft
from trl.gtfs import load_schedule
from trl.orchestration import RunService
from trl.scenarios import load_scenario
from trl.storage import RunStore

OUT = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures"


async def build(store: RunStore) -> dict[str, dict[str, object]]:
    service = RunService(store, load_schedule())
    notice = load_scenario().notice
    runs: dict[str, str] = {}

    def create(name: str, **options: object) -> str:
        receipt = service.new_run(CreateRun.model_validate(options), f"create-{name}")
        runs[name] = receipt.run_id
        return receipt.run_id

    verified = create("verified")
    work = store.command(verified, "report", Disrupt(version=0, notice=notice))
    await service.execute(work)

    clarifying = create("clarification", workflow="vnext")
    work = store.command(
        clarifying,
        "report",
        Disrupt(version=0, notice="Konak İskele tram stop closed until 10:00."),
    )
    await service.execute(work)

    pending = create("planning_pending_call")
    work = store.command(pending, "report", Disrupt(version=0, notice=notice))
    store.reserve_call(pending, work.version, "pending", "model", "digest", 4096)

    failed = create("model_error")
    work = store.command(failed, "report", Disrupt(version=0, notice=notice))
    store.step(
        failed,
        work.version,
        "model-error",
        updates={"status": "model_error", "error": "model_unavailable"},
        event=EventDraft(
            kind="error", role="system", message="The local model could not decide."
        ),
    )

    superseded = create("superseded")
    store.command(superseded, "first", Disrupt(version=0, notice=notice))
    store.command(superseded, "second", Disrupt(version=1, notice=notice + " Update."))

    abstained = create("abstained", workflow="vnext")
    work = store.command(
        abstained,
        "report",
        Disrupt(version=0, notice="Konak İskele tram stop closed until 10:00."),
    )
    await service.execute(work)
    question = store.view(abstained).evidence
    assert question and question.intake and question.intake.question
    answered = store.command(
        abstained,
        "answer",
        Clarify(version=1, question_id=question.intake.question.id, answer="08:24 UTC"),
    )
    await service.execute(answered)

    snapshot: dict[str, dict[str, object]] = {}
    for name, run_id in runs.items():
        snapshot[name] = {
            "run_id": run_id,
            "view": json.loads(store.view(run_id).model_dump_json()),
            "events": [
                json.loads(item.model_dump_json()) for item in store.events(run_id, 0)
            ],
        }
    return snapshot


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "v1.2.0.sqlite"
        store = RunStore(path)
        snapshot = asyncio.run(build(store))
        with sqlite3.connect(path) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            dump = "\n".join(connection.iterdump())
    if version != 2:
        sys.exit(f"Expected schema version 2, found {version}.")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v1_2_0.sql").write_text(dump + "\n")
    (OUT / "v1_2_0.expected.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    print(f"Wrote {len(snapshot)} runs.")


if __name__ == "__main__":
    main()
