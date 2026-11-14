"""Drive the run lifecycle with random command sequences, restarts and stale writers."""

import asyncio
import shutil
import tempfile
from contextlib import closing
from pathlib import Path

import pytest
from hypothesis import Phase, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
)

from trl import dbtools
from trl.contracts import CreateRun, Disrupt, Receipt, Retract, Retry
from trl.disruptions import Overlay
from trl.domain import Disruption, StopClosure
from trl.gtfs import load_schedule
from trl.lifecycle import SETTLED
from trl.orchestration import RunService
from trl.scenarios import load_scenario
from trl.storage import Conflict, Fence, Fenced, RunStore, current_fence
from trl.verify import verify_offer

SCHEDULE = load_schedule()
DAY = load_scenario().service_date
GOOD = {
    load_scenario().notice: None,
    "Karataş tram stop is closed from 08:00 to 08:10.": None,
}
BAD = "Something happened near the harbour."
NOTICES = [*GOOD, BAD]


class RunLifecycle(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.directory = Path(tempfile.mkdtemp(prefix="trl-state-"))
        self.path = self.directory / "runs.sqlite"
        self.store = RunStore(self.path)
        self.service = RunService(self.store, SCHEDULE)
        self.keys = 0
        self.runs: list[str] = []
        self.versions: dict[str, int] = {}
        self.incidents: dict[str, list[Disruption]] = {}
        self.pending: dict[str, list[Disruption] | None] = {}

    def teardown(self) -> None:
        shutil.rmtree(self.directory, ignore_errors=True)

    def key(self) -> str:
        self.keys += 1
        return f"k{self.keys}"

    def drain(self, run_id: str) -> None:
        run = self.store.read(run_id)
        if run.status == "planning":
            asyncio.run(self.service.execute(Receipt(run_id=run_id, version=run.version)))

    @initialize()
    def first_run(self) -> None:
        self.create()

    @rule()
    def create(self) -> None:
        receipt = self.service.new_run(CreateRun(), self.key())
        self.runs.append(receipt.run_id)
        self.versions[receipt.run_id] = 0
        self.incidents[receipt.run_id] = []

    @rule(data=st.data(), notice=st.sampled_from(NOTICES), mode=st.sampled_from(["add", "replace"]))
    def disrupt(self, data: st.DataObject, notice: str, mode: str) -> None:
        run_id = data.draw(st.sampled_from(self.runs))
        current = self.store.read(run_id).version
        request = Disrupt.model_validate({"version": current, "notice": notice, "mode": mode})
        receipt = self.store.command(run_id, self.key(), request)
        assert receipt.version == current + 1
        before = [] if mode == "replace" else list(self.incidents[run_id])
        self.drain(run_id)
        run = self.store.read(run_id)
        assert run.status != "planning"
        recorded = tuple(run.overlays)
        # A report records at most one incident, never drops one it was not told to replace.
        assert recorded == tuple(before) or (
            len(recorded) == len(before) + 1 and recorded[:-1] == tuple(before)
        )
        if notice == BAD:
            assert recorded == tuple(before)
        self.incidents[run_id] = list(recorded)
        self.versions[run_id] = run.version

    @rule(data=st.data())
    def stale_version_is_refused(self, data: st.DataObject) -> None:
        run_id = data.draw(st.sampled_from(self.runs))
        current = self.store.read(run_id).version
        before = self.store.view(run_id)
        with pytest.raises(Conflict):
            self.store.command(run_id, self.key(), Disrupt(version=current + 1, notice=NOTICES[0]))
        assert self.store.view(run_id) == before

    @rule(data=st.data())
    def retract_one(self, data: st.DataObject) -> None:
        run_id = data.draw(st.sampled_from(self.runs))
        run = self.store.read(run_id)
        if not run.overlays:
            with pytest.raises(Conflict):
                self.store.command(
                    run_id, self.key(), Retract(version=run.version, incident_ids=("x",))
                )
            return
        view = self.store.view(run_id)
        target = data.draw(st.sampled_from(view.incidents))
        self.store.command(
            run_id, self.key(), Retract(version=run.version, incident_ids=(target.id,))
        )
        self.drain(run_id)
        expected = [item for item in self.incidents[run_id] if item != target.disruption]
        assert list(self.store.read(run_id).overlays) == expected
        self.incidents[run_id] = expected

    @rule(data=st.data())
    def retry_when_allowed(self, data: st.DataObject) -> None:
        run_id = data.draw(st.sampled_from(self.runs))
        view = self.store.view(run_id)
        request = Retry(version=view.version)
        if view.retryable:
            self.store.command(run_id, self.key(), request)
            self.drain(run_id)
        else:
            with pytest.raises(Conflict):
                self.store.command(run_id, self.key(), request)

    @rule(data=st.data(), notice=st.sampled_from(NOTICES))
    def replay_and_conflict(self, data: st.DataObject, notice: str) -> None:
        run_id = data.draw(st.sampled_from(self.runs))
        version = self.store.read(run_id).version
        key = self.key()
        first = self.store.command(run_id, key, Disrupt(version=version, notice=notice))
        assert self.store.command(run_id, key, Disrupt(version=version, notice=notice)) == first
        other = NOTICES[(NOTICES.index(notice) + 1) % len(NOTICES)]
        with pytest.raises(Conflict):
            self.store.command(run_id, key, Disrupt(version=version, notice=other))
        self.drain(run_id)
        self.incidents[run_id] = list(self.store.read(run_id).overlays)

    @rule()
    def restart(self) -> None:
        self.store = RunStore(self.path)
        self.service = RunService(self.store, SCHEDULE)

    @rule(data=st.data())
    def late_writer_changes_nothing(self, data: st.DataObject) -> None:
        run_id = data.draw(st.sampled_from(self.runs))
        before = self.store.view(run_id)
        events = self.store.events(run_id, 0)
        token = current_fence.set(Fence(run_id, -1))
        try:
            with closing(self.store.connect()) as connection:
                connection.execute(
                    "INSERT INTO leases (run_id, version, token) VALUES (?,?,5) "
                    "ON CONFLICT(run_id) DO NOTHING",
                    (run_id, before.version),
                )
                connection.commit()
            with pytest.raises(Fenced):
                self.store.step(run_id, before.version, "late", updates={"status": "planning"})
        finally:
            current_fence.reset(token)
        assert self.store.view(run_id) == before
        assert self.store.events(run_id, 0) == events

    @invariant()
    def database_is_consistent(self) -> None:
        assert dbtools.invariants(self.path) == []

    @invariant()
    def versions_only_increase(self) -> None:
        for run_id in self.runs:
            run = self.store.read(run_id)
            assert run.version >= self.versions[run_id]
            self.versions[run_id] = run.version

    @invariant()
    def settled_runs_hold_no_live_lease(self) -> None:
        assert dbtools.live_leases(self.path) == []

    @invariant()
    def verified_means_two_votes_and_a_passing_check(self) -> None:
        for run_id in self.runs:
            view = self.store.view(run_id)
            if view.status != "verified":
                continue
            offer = next(item for item in view.offers if item.id == view.verified_offer)
            assert {vote.rider for vote in view.votes if vote.accepted} == {"a", "b"}
            run = self.store.read(run_id)
            assert (
                verify_offer(
                    SCHEDULE,
                    run.scenario,
                    offer,
                    view.votes,
                    run.version,
                    Overlay.compile(run.overlays),
                )
                is None
            )

    @invariant()
    def incidents_match_the_model(self) -> None:
        for run_id in self.runs:
            run = self.store.read(run_id)
            if run.status in SETTLED or run.status in {"ready", "clarification"}:
                assert list(run.overlays) == self.incidents[run_id]
                assert all(isinstance(item, StopClosure) for item in run.overlays)

    @precondition(lambda self: bool(self.runs))
    @rule()
    def events_stay_ordered(self) -> None:
        for run_id in self.runs:
            sequence = [event.seq for event in self.store.events(run_id, 0, limit=10_000)]
            assert sequence == sorted(set(sequence))


TestRunLifecycle = RunLifecycle.TestCase
TestRunLifecycle.settings = settings(
    max_examples=8, stateful_step_count=8, deadline=None, phases=[Phase.generate, Phase.reuse]
)


@pytest.mark.deep
def test_run_lifecycle_long_sequences() -> None:
    long = type("LongRunLifecycle", (RunLifecycle,), {})
    long.TestCase.settings = settings(max_examples=1000, stateful_step_count=40, deadline=None)
    unittest_case = long.TestCase("runTest")
    unittest_case.runTest()
