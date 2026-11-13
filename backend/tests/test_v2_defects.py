"""Defects reproduced on v1.2.0 and tracked by the v2 engineering plan.

Each test states the intended v2 behavior. A strict expected failure marks a defect that is
still open: the test fails on the current behavior, and pytest reports an error if it starts
passing before the marker is removed. The commit that fixes a defect removes its marker.
"""

import asyncio
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from test_routing import EMPTY, network, small, votes

from trl import agents, orchestration, routing
from trl.contracts import CreateRun, Disrupt
from trl.disruptions import Overlay
from trl.domain import Constraint, Scenario, StopClosure
from trl.gtfs import Schedule, load_schedule
from trl.intake import answer_facts, decide, extract
from trl.notice import rule_notice
from trl.orchestration import RunService
from trl.routing import find_offers
from trl.scenarios import load_scenario
from trl.storage import RunStore
from trl.verify import verify_offer
from trl.vnext import Extraction, ExtractionQuote, Intake

SCHEDULE: Schedule = load_schedule()
DAY: date = load_scenario().service_date
KONAK_ISKELE = "tram:7"
MORNING = (8 * 3600 + 24 * 60, 10 * 3600)


def infeasible(_: object) -> tuple[str, None]:
    return "infeasible", None


def intake(text: str, proposal: Extraction | None = None) -> Intake:
    facts, reasons = extract(text, SCHEDULE, DAY, proposal)
    return decide(facts, reasons, SCHEDULE, DAY, infeasible, 1)  # pyright: ignore[reportArgumentType]


def closure(decision: Intake) -> tuple[int, int] | None:
    if decision.action != "apply" or decision.selected is None:
        return None
    incident = decision.selected.incident
    return (incident.start, incident.end) if isinstance(incident, StopClosure) else None


def slot_values(text: str, slot: str) -> list[object]:
    facts, _ = extract(text, SCHEDULE, DAY)
    return [item.value for item in facts if item.slot == slot]


def running_trip() -> str:
    return next(trip.id for trip in SCHEDULE.trips.values() if SCHEDULE.runs(trip.service, DAY))


OTHER_DATES = (
    "Konak İskele tram stop is closed from 08:24 to 10:00 on 14.11.2026.",
    "Konak İskele tramvay durağı 22 Ekim'de 08:24 - 10:00 arası kapalı.",
    "Konak İskele tram stop is closed from 08:24 to 10:00 next Friday.",
    "Konak İskele tram stop is closed 2030-01-01T08:24 to 10:00.",
)


@pytest.mark.xfail(strict=True, reason="V2-C1: non-ISO or T-separated dates bypass the guard")
@pytest.mark.parametrize("notice", OTHER_DATES)
def test_c1_notice_for_another_day_is_never_applied(notice: str) -> None:
    assert intake(notice).action == "abstain"
    assert rule_notice(notice, SCHEDULE, DAY) is None


def test_c1_notice_for_the_service_day_still_applies() -> None:
    notice = "Konak İskele tram stop is closed from 08:24 to 10:00 on 2026-10-21."
    assert closure(intake(notice)) == MORNING


@pytest.mark.xfail(strict=True, reason="V2-C2: an ISO offset is read as a clock time")
def test_c2_local_offset_is_not_a_clock_time() -> None:
    notice = "Konak İskele tram stop is closed from 2026-10-21T08:24:00+03:00 to 10:00."
    assert closure(intake(notice)) == MORNING
    legacy = rule_notice(notice, SCHEDULE, DAY)
    assert legacy is None or (isinstance(legacy, StopClosure) and legacy.start == MORNING[0])


@pytest.mark.xfail(strict=True, reason="V2-C3: Turkish suffix and preposition binding")
@pytest.mark.parametrize(
    "notice",
    [
        "Konak İskele tramvay durağı 08:24'ten 10:00'a kadar kapalı.",
        "Konak İskele tramvay durağı 08.24 ile 10.00 arasında kapalı.",
        "Konak İskele tram stop is closed until 10:00 from 08:24.",
    ],
)
def test_c3_closure_ranges_bind_start_and_end(notice: str) -> None:
    assert closure(intake(notice)) == MORNING


@pytest.mark.xfail(strict=True, reason="V2-C3: a lone end time is read as the start")
@pytest.mark.parametrize(
    "notice",
    [
        "Konak İskele tramvay durağı saat 10:00'a kadar kapalı.",
        "Konak İskele tram stop is closed before 10:00.",
    ],
)
def test_c3_lone_end_time_binds_to_end(notice: str) -> None:
    assert slot_values(notice, "end") == [MORNING[1]]
    assert slot_values(notice, "start") == []


@pytest.mark.xfail(strict=True, reason="V2-C4: meridiem applies to one side of a range")
def test_c4_meridiem_carries_across_a_short_range() -> None:
    notice = "Konak İskele tram stop is closed from 8:24 to 10:00 pm."
    assert closure(intake(notice)) == (20 * 3600 + 24 * 60, 22 * 3600)


@pytest.mark.xfail(strict=True, reason="V2-C4: decimal comma in a Turkish duration")
def test_c4_decimal_comma_duration() -> None:
    notice = f"{running_trip()} seferi 1,5 saat gecikmeli."
    assert slot_values(notice, "delay") == [5400]


@pytest.mark.xfail(strict=True, reason="V2-C4: an overnight range ends after midnight")
def test_c4_overnight_closure_uses_service_day_seconds() -> None:
    notice = "Konak İskele tram stop is closed from 23:30 to 00:30."
    assert closure(intake(notice)) == (23 * 3600 + 30 * 60, 24 * 3600 + 30 * 60)


def dwell_case() -> tuple[Schedule, Scenario, Overlay]:
    schedule = network([("a", "c", 0, 5), ("c", "d", 12, 15), ("b", "d", 0, 14)])
    scenario = small().model_copy(
        update={
            "a": Constraint(stop="a", ready=0, wait_limit=6, transfer_limit=2),
            "b": Constraint(stop="b", ready=0, wait_limit=6, transfer_limit=2),
        }
    )
    return schedule, scenario, Overlay.compile((StopClosure(stop="c", start=6, end=10),))


def test_c5_router_rejects_waiting_through_a_closure() -> None:
    schedule, scenario, closed = dwell_case()
    assert find_offers(schedule, scenario, overlay=closed) == []


def test_c5_verifier_rejects_waiting_through_a_closure() -> None:
    schedule, scenario, closed = dwell_case()
    offer = find_offers(schedule, scenario, overlay=EMPTY)[0]
    assert verify_offer(schedule, scenario, offer, votes(offer), 0, closed) is not None


def test_c6_replacement_report_retracts_the_previous_incident(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "replace.sqlite")
    service = RunService(store, SCHEDULE)
    receipt = service.new_run(CreateRun(), "create")
    first = store.command(
        receipt.run_id,
        "first",
        Disrupt(version=0, notice="Konak İskele tram stop is closed from 08:24 to 10:00."),
    )
    asyncio.run(service.execute(first))
    second = store.command(
        receipt.run_id,
        "second",
        Disrupt.model_validate(
            {
                "version": 1,
                "notice": "Konak İskele tram stop is closed from 08:24 to 09:00.",
                "mode": "replace",
            }
        ),
    )
    asyncio.run(service.execute(second))
    view = store.view(receipt.run_id).model_dump()
    assert [item["disruption"] for item in view["incidents"]] == [
        {"kind": "stop_closure", "stop": KONAK_ISKELE, "start": MORNING[0], "end": 32400}
    ]


@pytest.mark.xfail(strict=True, reason="V2-C7: identifiers are case-insensitive")
def test_c7_uppercase_identifier_resolves() -> None:
    decision = intake("TRAM:7 is closed from 08:24 to 10:00.")
    assert decision.selected is not None
    assert decision.selected.incident == StopClosure(
        stop=KONAK_ISKELE, start=MORNING[0], end=MORNING[1]
    )


def test_l1_exhausted_initial_search_is_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(routing, "MAX_LABELS", 1)
    store = RunStore(tmp_path / "budget.sqlite")
    receipt = RunService(store, SCHEDULE).new_run(CreateRun(), "create")
    assert store.view(receipt.run_id).status == "search_incomplete"


def test_l2_invalid_status_is_never_persisted(tmp_path: Path) -> None:
    store = RunStore(tmp_path / "status.sqlite")
    service = RunService(store, SCHEDULE)
    receipt = service.new_run(CreateRun(), "create")
    work = store.command(receipt.run_id, "report", Disrupt(version=0, notice="Konak closed."))
    try:
        store.step(receipt.run_id, work.version, "bogus", updates={"status": "bogus"})
    except (TypeError, ValueError):
        pass
    assert store.view(receipt.run_id).status != "bogus"


def test_l2_internal_failure_is_a_system_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = RunStore(tmp_path / "internal.sqlite")
    service = RunService(store, SCHEDULE)
    receipt = service.new_run(CreateRun(), "create")

    def broken(*_: object, **__: object) -> list[object]:
        raise RuntimeError("internal")

    monkeypatch.setattr(orchestration, "find_offers", broken)
    work = store.command(
        receipt.run_id, "report", Disrupt(version=0, notice=load_scenario().notice)
    )
    asyncio.run(service.execute(work))
    assert store.view(receipt.run_id).status == "system_error"


def test_l4_newer_schema_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "newer.sqlite"
    RunStore(path)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError):
        RunStore(path)


@pytest.mark.xfail(strict=True, reason="V2-L6: only one clarification round is supported")
def test_l6_second_missing_slot_gets_a_second_question() -> None:
    facts, reasons = extract("Konak İskele tram stop is closed.", SCHEDULE, DAY)
    first = decide(facts, reasons, SCHEDULE, DAY, infeasible, 1)  # pyright: ignore[reportArgumentType]
    assert first.question is not None and first.question.slot == "start"
    answered = answer_facts(first, "08:24", None, SCHEDULE, DAY)
    second = decide(answered, (), SCHEDULE, DAY, infeasible, 1, answered=True)  # pyright: ignore[reportArgumentType]
    assert second.action == "ask"
    assert second.question is not None and second.question.slot == "end"


@pytest.mark.xfail(strict=True, reason="V2-L7: verified model quotes are limited to a whitelist")
def test_l7_verified_model_quote_can_supply_the_event_kind() -> None:
    notice = "Konak İskele tram stop is shuttered from 08:24 to 10:00."
    quote = ExtractionQuote.model_validate(
        {"slot": "kind", "quote": "shuttered", "kind": "stop_closure"}
    )
    assert closure(intake(notice, Extraction(quotes=(quote,)))) == MORNING


@pytest.mark.xfail(strict=True, reason="V2-L7: a quote from a negated clause must not apply")
def test_l7_model_quote_in_a_negated_clause_is_rejected() -> None:
    notice = "Konak İskele tram stop is not shuttered; service runs from 08:24 to 10:00."
    quote = ExtractionQuote.model_validate(
        {"slot": "kind", "quote": "shuttered", "kind": "stop_closure"}
    )
    assert intake(notice, Extraction(quotes=(quote,))).action != "apply"


@pytest.mark.xfail(strict=True, reason="V2-L8: negation outside the event clause abstains")
def test_l8_unrelated_negation_does_not_block_the_event() -> None:
    notice = "Konak İskele tram stop is closed from 08:24 to 10:00 (no lifts)."
    assert closure(intake(notice)) == MORNING


@pytest.mark.xfail(strict=True, reason="V2-L8: conjoined stops are separate events")
def test_l8_conjoined_closures_apply_together() -> None:
    notice = "Konak İskele and Karataş tram stops are closed from 08:24 to 10:00."
    assert intake(notice).action == "apply"


@pytest.mark.xfail(strict=True, reason="V2-L9: prompt content must be part of the digest")
def test_l9_prompt_content_changes_the_request_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    view: agents.RoleView = {"notice": "Konak İskele closed."}
    before = agents.view_digest("operator_vnext", view)
    for prompt in agents.PROMPT_DIR.glob("*.md"):
        (tmp_path / prompt.name).write_text(prompt.read_text() + "\nRevised.\n")
    monkeypatch.setattr(agents, "PROMPT_DIR", tmp_path)
    assert agents.view_digest("operator_vnext", view) != before
