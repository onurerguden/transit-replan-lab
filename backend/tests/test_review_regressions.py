import asyncio
from pathlib import Path

import pytest
from test_routing import EMPTY, network, small, votes

from trl.agents import Choice, ModelError
from trl.contracts import CreateRun, Disrupt, EventDraft
from trl.disruptions import Overlay
from trl.domain import Constraint, TripCancellation, Vote
from trl.gtfs import load_schedule
from trl.intake import answer_facts, decide, extract
from trl.orchestration import RunService
from trl.robustness import evaluate
from trl.routing import SearchStats, find_offers, transfer_margin
from trl.scenarios import load_scenario
from trl.storage import RunStore
from trl.verify import verify_offer


@pytest.mark.parametrize("answer", ["08:24 UTC", "08:24 GMT+1", "08:24 on 2030-01-01"])
def test_clarification_rejects_unsupported_time_context(answer: str) -> None:
    schedule, day = load_schedule(), load_scenario().service_date
    facts, reasons = extract("Konak İskele tram stop closed until 10:00.", schedule, day)
    intake = decide(facts, reasons, schedule, day, lambda _: ("infeasible", None), 1)
    assert intake.question and intake.question.slot == "start"
    facts = answer_facts(intake, answer, None, schedule, day)
    decision = decide(facts, (), schedule, day, lambda _: ("infeasible", None), 1, answered=True)
    assert decision.action == "abstain" and decision.selected is None


def test_completed_revision_rejects_late_worker_writes(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "terminal.sqlite")
    service = RunService(store, load_schedule())
    receipt = service.new_run(CreateRun(), "create")
    work = store.command(
        receipt.run_id, "report", Disrupt(version=0, notice=load_scenario().notice)
    )
    slot = store.reserve_call(receipt.run_id, work.version, "pending", "model", "digest", 4096)
    assert slot is not None
    asyncio.run(service.execute(work))
    before = store.view(receipt.run_id)
    events = store.events(receipt.run_id, 0)
    assert before.status == "verified"
    assert not store.step(
        receipt.run_id,
        work.version,
        "worker-error",
        updates={"status": "model_error", "error": "worker_error"},
        event=EventDraft(kind="error", role="system", message="Late failure."),
    )
    assert store.reserve_call(receipt.run_id, work.version, "late", "model", "digest", 4096) is None
    calls = store.calls(receipt.run_id, work.version)
    assert not store.finish_call(receipt.run_id, work.version, slot, "error", None, 0, 0, 1)
    late = Vote(version=work.version, rider="a", offer_id="obsolete", accepted=True)
    assert not store.step(receipt.run_id, work.version, "late-vote", votes=(late,))
    assert store.calls(receipt.run_id, work.version) == calls
    assert store.view(receipt.run_id) == before
    assert store.events(receipt.run_id, 0) == events


def test_diverse_search_preserves_same_arrival_transfer_histories() -> None:
    schedule = network([("a", "b", 0, 2), ("b", "d", 3, 10), ("a", "c", 0, 5), ("c", "d", 9, 10)])
    scenario = small().model_copy(update={"b": Constraint(stop="d", ready=10, wait_limit=6)})
    offers = find_offers(schedule, scenario, diverse=True, margin_aware=True)
    margins = [margin[0] for offer in offers if (margin := transfer_margin(offer.a.legs))]
    assert max(margins) == 4
    assert all(
        verify_offer(schedule, scenario, offer, votes(offer), 0, EMPTY) is None for offer in offers
    )


def test_equal_margin_paths_can_have_different_delay_outcomes() -> None:
    schedule = network([("a", "b", 0, 2), ("b", "d", 3, 10), ("a", "c", 0, 5), ("c", "d", 6, 10)])
    scenario = small().model_copy(update={"b": Constraint(stop="d", ready=10, wait_limit=6)})
    stats = SearchStats()
    offers = find_offers(schedule, scenario, diverse=True, margin_aware=True, stats=stats)
    selected = next(offer for offer in offers if len(offer.a.legs) == 2)
    first = selected.a.legs[0]
    assert first.kind == "ride"
    delay = {(first.trip, first.service_date): 2}
    assert evaluate(schedule, scenario, selected, EMPTY, delay)[1] is not None
    omit_first = Overlay.compile(
        (TripCancellation(trip=first.trip, service_date=first.service_date),)
    )
    alternate = find_offers(schedule, scenario, overlay=omit_first)[0]
    assert transfer_margin(selected.a.legs) == (1, first)
    margin = transfer_margin(alternate.a.legs)
    assert margin is not None and margin[0] == 1
    # The scenario's perturbation is specific to the incoming trip, not to slack.
    assert evaluate(schedule, scenario, alternate, EMPTY, delay) == (10, None)
    assert stats.labels > 0 and stats.pairs > 0


def test_cached_decision_requires_the_same_role_view(tmp_path: Path) -> None:
    async def exercise() -> None:
        store = RunStore(tmp_path / "cache.sqlite")
        service = RunService(store, load_schedule())
        receipt = service.new_run(CreateRun(), "create")
        work = store.command(
            receipt.run_id, "report", Disrupt(version=0, notice=load_scenario().notice)
        )
        run = store.read(work.run_id)
        first = await service.negotiator.ask(
            run, "first", "first:a", {"offers": [{"id": "v1-1"}]}, Choice
        )
        again = await service.negotiator.ask(
            run, "first", "first:a", {"offers": [{"id": "v1-1"}]}, Choice
        )
        assert first == again and len(store.calls(run.id, run.version)) == 1
        with pytest.raises(ModelError, match="request_mismatch"):
            await service.negotiator.ask(
                run, "first", "first:a", {"offers": [{"id": "v1-2"}]}, Choice
            )

    asyncio.run(exercise())
