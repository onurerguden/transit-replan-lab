import asyncio
import os
from pathlib import Path

import pytest

from trl.agents import ModelReply, OllamaModel, ReplayModel, RoleView, Stage, view_for
from trl.contracts import CreateRun, Disrupt, RunBody
from trl.domain import Record
from trl.gtfs import load_schedule
from trl.orchestration import RunService
from trl.scenarios import load_scenario
from trl.storage import Conflict, RunStore


def test_role_views_isolate_first_preferences() -> None:
    schedule = load_schedule()
    scenario = load_scenario()
    run = RunBody(
        id="isolated", architecture="five", counteroffers=True, scenario=scenario, initial=None
    )
    a = view_for("first", run, schedule, rider="a", choices=("other-first-pick",))
    b = view_for("first", run, schedule, rider="b")
    mediator = view_for("mediator", run, schedule, choices=("shared-pick",))
    assert set(a) == set(b) == {"rider", "constraints", "offers"}
    assert a["constraints"] != b["constraints"]
    assert "other-first-pick" not in str(a)
    assert "constraints" not in mediator
    assert not {"notice", "stops"} & a.keys()


@pytest.mark.parametrize("architecture", ["single", "three", "five"])
def test_replay_verifies_two_current_acceptances(tmp_path: Path, architecture: str) -> None:
    async def exercise() -> None:
        schedule = load_schedule()
        store = RunStore(tmp_path / "state.sqlite")
        service = RunService(store, schedule, ReplayModel(schedule))
        command = CreateRun.model_validate({"architecture": architecture})
        run = service.new_run(command, "start")
        receipt = store.command(
            run.run_id, "incident", Disrupt(version=0, notice=load_scenario().notice)
        )
        await service.execute(receipt)
        view = store.view(run.run_id)
        assert view.status == "verified", view
        assert {(v.rider, v.version, v.offer_id, v.accepted) for v in view.votes} == {
            ("a", 1, view.verified_offer, True),
            ("b", 1, view.verified_offer, True),
        }
        assert 2 <= view.metrics.calls <= 10
        if architecture == "five":
            assert {"analyst", "mediator"} <= {event.role for event in store.events(run.run_id, 0)}

    asyncio.run(exercise())


def test_reservations_enforce_budget_and_ignore_stale_completion(tmp_path: Path) -> None:
    schedule = load_schedule()
    store = RunStore(tmp_path / "state.sqlite")
    run = RunService(store, schedule).new_run(CreateRun(), "start")
    scenario = load_scenario()
    command = Disrupt(version=0, notice=scenario.notice)
    store.command(run.run_id, "one", command)
    slots = [
        store.reserve_call(run.run_id, 1, f"step:{n}", "model", "digest", 4096) for n in range(10)
    ]
    with pytest.raises(Conflict, match="budget"):
        store.reserve_call(run.run_id, 1, "overflow", "model", "digest", 4096)
    store.command(run.run_id, "two", command.model_copy(update={"version": 1}))
    assert store.reserve_call(run.run_id, 1, "late", "model", "digest", 4096) is None
    assert slots[0] is not None
    assert not store.finish_call(run.run_id, 1, slots[0], "valid", "{}", 3, 2, 5)
    assert store.calls(run.run_id, 1)[0].state == "pending"
    assert store.view(run.run_id).metrics.calls == 0


@pytest.mark.ollama
def test_real_ollama_feasible_and_infeasible(tmp_path: Path) -> None:
    async def exercise() -> None:
        schedule = load_schedule()
        store = RunStore(tmp_path / "real.sqlite")
        model = OllamaModel(os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
        service = RunService(store, schedule, model)
        signatures: list[list[tuple[str, str, str]]] = []
        for key, scenario, expected in (
            ("valid-1", "demo", "verified"),
            ("valid-2", "demo", "verified"),
            ("impossible", "infeasible", "infeasible"),
        ):
            request = CreateRun.model_validate({"scenario": scenario, "architecture": "five"})
            run = service.new_run(request, key)
            receipt = store.command(
                run.run_id,
                "close",
                Disrupt(version=0, notice=store.read(run.run_id).scenario.notice),
            )
            await service.execute(receipt)
            view = store.view(run.run_id)
            evidence = store.calls(run.run_id, 1)
            assert view.status == expected, (view.error, view.status, evidence)
            assert 0 < view.metrics.calls <= 10
            assert view.metrics.output_tokens > 0
            signatures.append(
                [(event.kind, event.role, event.message) for event in store.events(run.run_id, 0)]
            )
            print(key, view.status, view.metrics.model_dump_json())
        print("fixed-seed event order matched:", signatures[0] == signatures[1])

    asyncio.run(exercise())


def test_operator_cannot_guess_between_named_platforms(tmp_path: Path) -> None:
    async def exercise() -> None:
        schedule = load_schedule()

        class Overconfident(ReplayModel):
            async def generate(
                self,
                stage: Stage,
                view: RoleView,
                schema: type[Record],
                repair: bool,
            ) -> ModelReply:
                return ModelReply(
                    '{"kind":"stop_closure","stop":"tram:7","start":"08:24","end":"10:00"}',
                    5,
                    4,
                )

        store = RunStore(tmp_path / "ambiguous.sqlite")
        service = RunService(store, schedule, Overconfident(schedule))
        run = service.new_run(CreateRun(architecture="five"), "start")
        receipt = store.command(
            run.run_id,
            "notice",
            Disrupt(version=0, notice="Konak is closed from 08:24 to 10:00."),
        )
        await service.execute(receipt)
        view = store.view(run.run_id)
        assert view.status == "clarification"
        assert view.incident is None and view.verified_offer is None
        assert not view.votes and view.metrics.calls == 1

    asyncio.run(exercise())
