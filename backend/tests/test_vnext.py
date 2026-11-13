from pathlib import Path
from unicodedata import normalize

import pytest
from fastapi.testclient import TestClient
from test_api_runs import wait

from trl.api.app import create_app
from trl.disruptions import Overlay
from trl.gtfs import load_schedule
from trl.intake import extract, hypotheses
from trl.robustness import compare, worlds
from trl.routing import find_offers
from trl.scenarios import load_scenario
from trl.vnext import Extraction, ExtractionQuote


def test_evidence_matches_original_unicode_and_rejects_invented_quotes() -> None:
    schedule = load_schedule()
    day = load_scenario().service_date
    notice = normalize("NFD", "Konak İskele tram stop is out of service 08:24\u201310:00.")
    proposal = Extraction(quotes=(ExtractionQuote(slot="kind", quote="out of service"),))
    facts, reasons = extract(notice, schedule, day, proposal)
    assert not reasons
    events, overflow = hypotheses(facts, schedule, day)
    assert not overflow and len(events) == 1
    target = next(item for item in events[0].facts if item.slot == "target")
    assert (
        target.span
        and normalize("NFC", notice[target.span.start : target.span.end]) == "Konak İskele"
    )

    invalid = Extraction(quotes=(ExtractionQuote(slot="kind", quote="closed"),))
    facts, _ = extract(notice, schedule, day, invalid)
    assert hypotheses(facts, schedule, day)[0] == ()


def test_vnext_ambiguity_is_read_only_and_question_survives_restart(tmp_path: Path) -> None:
    database = tmp_path / "run.sqlite"
    notice = load_scenario("resilience").notice
    with TestClient(create_app(database)) as client:
        response = client.post(
            "/v1/runs",
            json={"workflow": "vnext", "scenario": "resilience", "route_policy": "robust"},
            headers={"Idempotency-Key": "create"},
        )
        run_id = response.json()["run_id"]
        base = f"/v1/runs/{run_id}"
        client.post(
            f"{base}/disruptions",
            json={"version": 0, "notice": notice},
            headers={"Idempotency-Key": "notice"},
        )
        view = wait(client, run_id)
        assert view.status == "clarification" and view.incident is None and not view.offers
        assert view.evidence and view.evidence.intake
        assert {impact.status for impact in view.evidence.intake.impacts} == {
            "feasible",
            "infeasible",
        }
        question = view.evidence.intake.question
        assert question and question.slot == "target"
        option = next(item for item in question.options if item.value == "tram:7")
    with TestClient(create_app(database)) as client:
        headers = {"Idempotency-Key": "answer"}
        body = {"version": 1, "question_id": question.id, "option_id": option.id}
        assert (
            client.post(
                f"{base}/clarifications",
                json={**body, "question_id": "old"},
                headers={"Idempotency-Key": "stale"},
            ).status_code
            == 409
        )
        first = client.post(f"{base}/clarifications", json=body, headers=headers)
        assert first.status_code == 202
        assert (
            client.post(f"{base}/clarifications", json=body, headers=headers).json() == first.json()
        )
        assert (
            client.post(
                f"{base}/clarifications", json=body, headers={"Idempotency-Key": "second"}
            ).status_code
            == 409
        )
        view = wait(client, run_id)
        assert view.status == "verified" and view.metrics.calls == 0
        assert view.evidence and view.evidence.offers[0].successful == 128
        assert {vote.offer_id for vote in view.votes} == {view.verified_offer}
        assert len(view.votes) == 2


def test_shared_worlds_and_batched_verdicts_match_serial(tmp_path: Path) -> None:
    schedule, scenario = load_schedule(), load_scenario()
    overlay = Overlay.compile((scenario.incident,))
    initial = find_offers(schedule, scenario, limit=1)[0]
    offers = tuple(find_offers(schedule, scenario, 1, overlay, diverse=True, initial=initial))
    profile = worlds(schedule, scenario, overlay)
    assert len(profile) == 128 and profile[:32] == ({},) * 32
    assert profile == worlds(schedule, scenario, overlay)
    assert len(offers) <= 24
    batched = compare(schedule, scenario, offers, overlay, initial, "robust")
    serial = compare(schedule, scenario, offers, overlay, initial, "robust", reuse_equivalent=False)
    assert batched == serial
    assert batched[1][0].successful > batched[1][1].successful


@pytest.mark.parametrize("feasibility_changes", [True, False])
def test_question_prioritizes_the_field_that_changes_feasibility(
    feasibility_changes: bool,
) -> None:
    from typing import Literal

    from trl.domain import Disruption, Offer
    from trl.intake import decide
    from trl.vnext import Fact

    schedule, scenario = load_schedule(), load_scenario()
    nominal = find_offers(schedule, scenario, limit=1)[0]
    facts = (
        Fact(slot="kind", value="stop_closure"),
        Fact(slot="target", value="tram:7"),
        Fact(slot="target", value="tram:8"),
        Fact(slot="start", value=30000),
        Fact(slot="end", value=31000),
        Fact(slot="end", value=36000),
    )

    def evaluate(incident: Disruption) -> tuple[Literal["feasible", "infeasible"], Offer | None]:
        assert incident.kind == "stop_closure"
        if incident.end == 31000:
            return "feasible", nominal
        if feasibility_changes:
            return "infeasible", None
        return "feasible", nominal.model_copy(update={"meeting": nominal.meeting + 60})

    targeted = decide(facts, (), schedule, scenario.service_date, evaluate, 1)
    fixed = decide(facts, (), schedule, scenario.service_date, evaluate, 1, strategy="fixed")
    assert targeted.question and targeted.question.slot == "end"
    assert fixed.question and fixed.question.slot == "target"
    assert len(targeted.impacts) == 4


def test_interrupted_hybrid_call_consumes_the_message_budget(tmp_path: Path) -> None:
    import asyncio

    from trl.contracts import CreateRun, Disrupt
    from trl.orchestration import RunService
    from trl.storage import RunStore

    schedule = load_schedule()
    store = RunStore(tmp_path / "reserved.sqlite")
    service = RunService(store, schedule)
    receipt = service.new_run(CreateRun(workflow="vnext", operator_mode="hybrid"), "create")
    work = store.command(
        receipt.run_id,
        "disruption",
        Disrupt(version=0, notice="Konak İskele is out of service from 08:24 to 10:00."),
    )
    assert store.reserve_call(
        receipt.run_id, work.version, "operator:source", "replay", "fake", 4096
    )
    asyncio.run(service.execute(work))
    state = store.view(receipt.run_id)
    assert state.status == "model_error" and state.error == "model_interrupted"
    assert state.metrics.calls == 1 and state.incident is None and not state.votes


@pytest.mark.ollama
def test_real_vnext_hybrid_grounds_a_report_and_recovers_a_meeting(tmp_path: Path) -> None:
    import asyncio
    import os

    from trl.agents import MODEL, OllamaModel
    from trl.contracts import CreateRun, Disrupt
    from trl.orchestration import RunService
    from trl.storage import RunStore

    schedule = load_schedule()
    store = RunStore(tmp_path / "ollama.sqlite")
    model = OllamaModel(
        os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        model=os.environ.get("TRL_OLLAMA_MODEL", MODEL),
    )
    service = RunService(store, schedule, model)
    run = service.new_run(
        CreateRun(workflow="vnext", operator_mode="hybrid", route_policy="robust"), "create"
    )
    work = store.command(
        run.run_id,
        "disrupt",
        Disrupt(version=0, notice="Konak İskele tram stop is out of service from 08:24 to 10:00."),
    )
    asyncio.run(service.execute(work))
    state = store.view(run.run_id)
    assert state.status == "verified"
    assert state.metrics.backend == "ollama" and state.metrics.calls == 1
    assert state.incident == load_scenario().incident and len(state.votes) == 2
