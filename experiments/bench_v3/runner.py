# pyright: basic
"""Read every report with each arm and score it against the generated gold."""

import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from trl.domain import Disruption
from trl.gtfs import Schedule
from trl.intake import (
    MAX_ROUNDS,
    answer_facts,
    conjoined_variants,
    decide,
    extract,
    lexicon_proposal,
)
from trl.vnext import Extraction, ExtractionQuote, Intake

from experiments.bench_v3.generate import Report

ARMS = ("rules", "lexicon", "model_ceiling", "model_adversarial")
Incident = tuple[object, ...]


@dataclass(frozen=True)
class Outcome:
    action: str
    incidents: frozenset[Incident]
    slot: str | None
    rounds: int


def key(incident: Disruption | dict[str, object]) -> Incident:
    data = incident if isinstance(incident, dict) else incident.model_dump(mode="json")
    kind = data["kind"]
    if kind == "stop_closure":
        return (kind, data["stop"], data["start"], data["end"])
    if kind == "trip_delay":
        return (kind, data["trip"], data["seconds"])
    return (kind, data["trip"])


REPLIES: dict[str, dict[str, str]] = {}


def replies(arm: str) -> dict[str, str]:
    """Raw model replies for an arm named `label=path`, loaded once."""
    if arm not in REPLIES:
        path = Path(arm.partition("=")[2])
        REPLIES[arm] = {
            row["id"]: row["reply"]
            for row in (json.loads(line) for line in path.read_text().splitlines())
        }
    return REPLIES[arm]


def parsed(reply: str) -> Extraction:
    """A reply that is not a valid extraction counts as no quote."""
    try:
        return Extraction.model_validate_json(reply.strip())
    except ValueError:
        return Extraction()


def proposal(arm: str, report: Report, rng: random.Random) -> Extraction | None:
    if "=" in arm:
        return (
            parsed(replies(arm).get(report.id, ""))
            if report.id in replies(arm)
            else None
        )
    if arm == "rules":
        return None
    if arm == "lexicon":
        return lexicon_proposal(report.text)
    if arm == "model_ceiling":
        gold = report.incidents[0]["kind"] if report.incidents else None
        if report.kind_phrase and gold:
            return Extraction(
                quotes=(
                    ExtractionQuote.model_validate(
                        {"slot": "kind", "quote": report.kind_phrase, "kind": gold}
                    ),
                )
            )
        return Extraction()
    words = re.findall(r"\w{4,}", report.text)
    kind = rng.choice(["stop_closure", "trip_delay", "trip_cancellation"])
    quote = rng.choice(words) if words else "xxxx"
    return Extraction(
        quotes=(
            ExtractionQuote.model_validate(
                {"slot": "kind", "quote": quote, "kind": kind}
            ),
        )
    )


def idle(_: Disruption) -> tuple[Literal["infeasible"], None]:
    return "infeasible", None


def read(report: Report, schedule: Schedule, day: date, arm: str) -> Outcome:
    rng = random.Random(report.id)
    guide = proposal(arm, report, rng)
    facts, reasons = extract(report.text, schedule, day, guide)
    if reasons == ("conflicting_targets",):
        variants = conjoined_variants(report.text, schedule, day)
        found: list[Disruption] = []
        for variant in variants:
            part = decide(
                *extract(variant, schedule, day, guide), schedule, day, idle, 1
            )
            if part.action == "apply" and part.selected:
                found.append(part.selected.incident)
        if variants and len(found) == len(variants):
            return Outcome("apply", frozenset(key(item) for item in found), None, 0)
    decision: Intake = decide(facts, reasons, schedule, day, idle, 1)
    first, slot, rounds = (
        decision.action,
        decision.question.slot if decision.question else None,
        0,
    )
    while decision.action == "ask" and rounds < MAX_ROUNDS and report.answer:
        rounds += 1
        facts = answer_facts(decision, report.answer, None, schedule, day)
        if not facts:
            decision = Intake(action="abstain", facts=(), reasons=("declined",))
            break
        decision = decide(
            facts, (), schedule, day, idle, 1, answered=rounds >= MAX_ROUNDS
        )
    incidents = (
        frozenset({key(decision.selected.incident)})
        if decision.action == "apply" and decision.selected
        else frozenset()
    )
    return Outcome(first, incidents, slot, rounds)


def score(report: Report, outcome: Outcome) -> dict[str, object]:
    gold = frozenset(key(item) for item in report.incidents)
    final_ok = (
        outcome.incidents == gold
        if report.action != "abstain"
        else not outcome.incidents
    )
    unsupported = bool(outcome.incidents) and (
        report.action == "abstain" or not outcome.incidents <= gold
    )
    return {
        "id": report.id,
        "group": report.group,
        "split": report.split,
        "lang": report.lang,
        "family": report.family,
        "cluster": "|".join(sorted(report.parts)),
        "gold_action": report.action,
        "action": outcome.action,
        "action_ok": outcome.action == report.action
        or (report.action == "apply" and outcome.action == "apply"),
        "final_ok": final_ok,
        "correct": outcome.action == report.action and final_ok,
        "unsupported": unsupported,
        "slot_ok": report.slot is None or outcome.slot == report.slot,
    }


def run(
    reports: list[Report],
    schedule: Schedule,
    day: date,
    arms: tuple[str, ...],
    write: Callable[[dict[str, object]], None],
) -> None:
    for arm in arms:
        for report in reports:
            write({"arm": arm, **score(report, read(report, schedule, day, arm))})


def load_rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]
