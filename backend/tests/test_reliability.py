import asyncio
import subprocess
import sys
from contextlib import closing
from pathlib import Path
from time import monotonic, sleep

import pytest
from fastapi.testclient import TestClient

from trl.agents import ModelReply, ReplayModel, RoleView, Stage
from trl.api.app import create_app
from trl.contracts import Clarify, CreateRun, Disrupt
from trl.domain import Record
from trl.gtfs import load_schedule
from trl.orchestration import RunService
from trl.scenarios import load_scenario
from trl.settings import get_settings
from trl.storage import Fence, Fenced, RunStore, current_fence


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


def test_crash_inside_reserved_model_call_can_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TRL_LEASE_TTL", "1")
    get_settings.cache_clear()
    path = tmp_path / "state.sqlite"
    store = RunStore(path)
    schedule = load_schedule()
    run = RunService(store, schedule).new_run(CreateRun(architecture="single"), "start")
    receipt = store.command(
        run.run_id,
        "close",
        Disrupt(version=0, notice=load_scenario().notice),
    )
    owner = subprocess.Popen(
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
from trl.storage import Fence, Fenced, RunStore, current_fence

class Crashing(ReplayModel):
    async def generate(self, *args, **kwargs):
        Path(sys.argv[3]).touch()
        while not Path(sys.argv[4]).exists():
            await asyncio.sleep(0.01)
        os.kill(os.getpid(), signal.SIGKILL)

schedule = load_schedule()
service = RunService(RunStore(Path(sys.argv[1])), schedule, Crashing(schedule))
asyncio.run(service.execute(Receipt.model_validate_json(sys.argv[2])))
""",
            str(path),
            receipt.model_dump_json(),
            str(tmp_path / "reserved"),
            str(tmp_path / "crash"),
        ],
    )
    try:
        deadline = monotonic() + 10
        while not (tmp_path / "reserved").exists():
            assert owner.poll() is None and monotonic() < deadline
            sleep(0.02)
        with TestClient(create_app(path)) as client:
            # Startup enqueues the planning revision in the second process.
            # It may not reserve a second call while the original owner is alive.
            sleep(0.25)
            assert [call.state for call in store.calls(run.run_id, 1)] == ["pending"]
            (tmp_path / "crash").touch()
            assert owner.wait(timeout=5) == -9
            while store.view(run.run_id).status == "planning":
                assert monotonic() < deadline
                sleep(0.02)
            assert client.get(f"/v1/runs/{run.run_id}").json()["status"] == "verified"
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)
    assert store.view(run.run_id).status == "verified"
    assert [call.state for call in store.calls(run.run_id, 1)] == ["pending", "valid", "valid"]
    assert sum(event.kind == "verified" for event in store.events(run.run_id, 0)) == 1


def test_answer_revokes_the_previous_owner_and_one_worker_finishes(tmp_path: Path) -> None:
    async def exercise() -> None:
        path = tmp_path / "handoff.sqlite"
        schedule = load_schedule()
        store = RunStore(path)
        service = RunService(store, schedule)
        run = service.new_run(CreateRun(workflow="vnext"), "start")
        work = store.command(
            run.run_id, "notice", Disrupt(version=0, notice="Konak is closed from 08:24 to 10:00.")
        )
        await service.execute(work)
        state = store.read(run.run_id)
        assert state.evidence and state.evidence.intake and state.evidence.intake.question
        question = state.evidence.intake.question
        reply = store.command(
            run.run_id,
            "answer",
            Clarify(version=work.version, question_id=question.id, answer="Konak İskele tram"),
        )
        # A worker that started before the answer still holds the old token.
        stale = Fence(run.run_id, store_token_before(store, run.run_id))
        token = current_fence.set(stale)
        try:
            with pytest.raises(Fenced):
                store.step(run.run_id, work.version, "late", updates={"status": "planning"})
        finally:
            current_fence.reset(token)
        await asyncio.wait_for(service.execute(reply), timeout=10)
        outcome = store.view(run.run_id)
        assert outcome.status == "verified"
        assert {vote.rider for vote in outcome.votes if vote.accepted} == {"a", "b"}
        assert sum(event.kind == "verified" for event in store.events(run.run_id, 0)) == 1

    asyncio.run(exercise())


def store_token_before(store: RunStore, run_id: str) -> int:
    """The token a worker held before the latest command revoked it."""
    with closing(store.connect()) as connection:
        row = connection.execute("SELECT token FROM leases WHERE run_id=?", (run_id,)).fetchone()
    return row["token"] - 1


def test_a_live_lease_blocks_a_second_owner_until_it_expires(tmp_path: Path) -> None:
    now = [1000.0]
    store = RunStore(tmp_path / "lease.sqlite", lease_ttl=10, clock=lambda: now[0])
    run = RunService(store, load_schedule()).new_run(CreateRun(), "start")
    store.command(run.run_id, "close", Disrupt(version=0, notice=load_scenario().notice))
    first = store.acquire_lease(run.run_id, 1, "one")
    assert first is not None
    assert store.acquire_lease(run.run_id, 1, "two") is None
    now[0] += 5
    assert store.heartbeat(first)
    now[0] += 9
    assert store.acquire_lease(run.run_id, 1, "two") is None
    now[0] += 2
    second = store.acquire_lease(run.run_id, 1, "two")
    assert second is not None and second.token > first.token
    assert not store.heartbeat(first)
