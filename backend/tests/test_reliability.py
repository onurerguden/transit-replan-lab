import asyncio
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from trl.agents import ModelReply, ReplayModel, RoleView, Stage
from trl.api.app import create_app
from trl.contracts import CreateRun, Disrupt
from trl.domain import Record
from trl.gtfs import load_schedule
from trl.orchestration import RunService
from trl.scenarios import load_scenario
from trl.storage import RunStore


def test_late_operator_reply_changes_no_application_table(tmp_path: Path) -> None:
    async def exercise() -> None:
        schedule = load_schedule()
        started = asyncio.Event()
        release = asyncio.Event()

        class Delayed(ReplayModel):
            async def generate(
                self,
                stage: Stage,
                view: RoleView,
                schema: type[Record],
                repair: bool,
            ) -> ModelReply:
                if not started.is_set():
                    started.set()
                    await release.wait()
                return await super().generate(stage, view, schema, repair)

        store = RunStore(tmp_path / "state.sqlite")
        service = RunService(store, schedule, Delayed(schedule))
        run = service.new_run(CreateRun(architecture="five"), "start")
        notice = load_scenario().notice
        first = store.command(run.run_id, "one", Disrupt(version=0, notice=notice))
        old_worker = asyncio.create_task(service.execute(first))
        await asyncio.wait_for(started.wait(), timeout=5)
        latest = store.command(run.run_id, "two", Disrupt(version=1, notice=notice))
        await service.execute(latest)
        snapshot = store.view(run.run_id)
        events = store.events(run.run_id, 0)
        old_calls = store.calls(run.run_id, 1)
        release.set()
        await old_worker
        assert snapshot.version == 2 and snapshot.status == "verified"
        assert store.view(run.run_id) == snapshot
        assert store.events(run.run_id, 0) == events
        assert store.calls(run.run_id, 1) == old_calls

    asyncio.run(exercise())


def test_schema_repair_is_bounded_and_cannot_verify(tmp_path: Path) -> None:
    async def exercise() -> None:
        schedule = load_schedule()

        class Broken(ReplayModel):
            async def generate(
                self,
                stage: Stage,
                view: RoleView,
                schema: type[Record],
                repair: bool,
            ) -> ModelReply:
                return ModelReply('{"invalid": true}', 5, 4)

        store = RunStore(tmp_path / "state.sqlite")
        service = RunService(store, schedule, Broken(schedule))
        run = service.new_run(CreateRun(architecture="five"), "start")
        receipt = store.command(
            run.run_id, "close", Disrupt(version=0, notice=load_scenario().notice)
        )
        await service.execute(receipt)
        view = store.view(run.run_id)
        assert view.status == "model_error" and view.error == "schema_error"
        assert view.verified_offer is None and not view.votes
        assert [call.state for call in store.calls(run.run_id, 1)] == ["invalid", "invalid"]

    asyncio.run(exercise())


def test_crash_inside_reserved_model_call_can_resume(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite"
    store = RunStore(path)
    schedule = load_schedule()
    run = RunService(store, schedule).new_run(CreateRun(architecture="single"), "start")
    receipt = store.command(
        run.run_id,
        "close",
        Disrupt(version=0, notice=load_scenario().notice),
    )
    crashed = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import asyncio
import os
import signal
import sys
from pathlib import Path
from trl.agents import ReplayModel
from trl.contracts import Receipt
from trl.gtfs import load_schedule
from trl.orchestration import RunService
from trl.storage import RunStore

class Crashing(ReplayModel):
    async def generate(self, *args, **kwargs):
        os.kill(os.getpid(), signal.SIGKILL)

schedule = load_schedule()
service = RunService(RunStore(Path(sys.argv[1])), schedule, Crashing(schedule))
asyncio.run(service.execute(Receipt.model_validate_json(sys.argv[2])))
""",
            str(path),
            receipt.model_dump_json(),
        ],
        check=False,
        timeout=15,
        capture_output=True,
    )
    assert crashed.returncode == -9, crashed.stderr
    assert store.calls(run.run_id, 1)[0].state == "pending"
    with TestClient(create_app(path)) as client:
        replay = client.get(f"/v1/runs/{run.run_id}/events")
        assert '"kind":"verified"' in replay.text
    assert store.view(run.run_id).status == "verified"
    assert [call.state for call in store.calls(run.run_id, 1)] == ["pending", "valid", "valid"]
