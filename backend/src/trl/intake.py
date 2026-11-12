"""Ground report fields and compare the plans implied by plausible incidents."""

import hashlib
import re
from collections.abc import Callable, Iterable
from datetime import date
from itertools import product
from typing import Literal

from trl.domain import Disruption, Offer, StopClosure, TripCancellation, TripDelay
from trl.gtfs import Schedule
from trl.notice import ACTIONS, IDENTIFIER, normalize, stop_candidates
from trl.vnext import Extraction, Fact, Hypothesis, Impact, Intake, Option, Question, Slot, Span

ORDER: tuple[Slot, ...] = ("target", "kind", "start", "end", "delay")
MAX_HYPOTHESES = 4
MAX_OPTIONS = 4
REQUIREMENTS: dict[str, tuple[Slot, ...]] = {
    "stop_closure": ("target", "start", "end"),
    "trip_cancellation": ("target",),
    "trip_delay": ("target", "delay"),
}
PROMPTS: dict[Slot, str] = {
    "target": "Which stop or trip is affected?",
    "kind": "What kind of disruption happened?",
    "start": "When does the closure start?",
    "end": "When does the closure end?",
    "delay": "How long is the delay?",
}
TIME = re.compile(r"(?<![\w:])(\d{1,2}):([0-5]\d)(?:\s*([ap])\.?m\.?)?(?![\w:])")
DURATION = re.compile(
    r"(?<![\w.+-])([0-9]{1,3})\s*(hours?|hrs?|saat|minutes?|mins?|dakika|seconds?|secs?|saniye)\b"
)
UNCERTAIN = re.compile(
    r"\b(?:no|not|never|maybe|might|possible|possibly|if|tomorrow|yesterday|"
    r"degil|belki|muhtemel\w*|yarin|dun|edilmedi|kapatilmadi|gecikmiyor)\b|n['\u2019]t\b|\?"
)
INDIRECT = {
    "stop_closure": re.compile(r"\b(?:out of service|erisime ara verildi|giris cikis yok)\b"),
    "trip_cancellation": re.compile(r"\b(?:taken off the timetable|seferden cekildi)\b"),
    "trip_delay": re.compile(r"\b(?:running behind|gec geliyor|geriden geliyor)\b"),
}
Source = Literal["notice", "answer"]
Evaluate = Callable[
    [Disruption], tuple[Literal["feasible", "infeasible", "search_incomplete"], Offer | None]
]


def fact(slot: Slot, value: str | int, text: str, start: int, end: int, source: Source) -> Fact:
    # Regex offsets are Python Unicode code points. Preserve source slices through normalization.
    return Fact(slot=slot, value=value, span=span_at(text, start, end, source))


def folded(text: str) -> tuple[str, list[int]]:
    characters: list[str] = []
    offsets: list[int] = []
    for index, char in enumerate(text):
        normalized = normalize(char)
        characters.append(normalized)
        offsets.extend([index] * len(normalized))
    return "".join(characters), offsets


def span_at(text: str, start: int, end: int, source: Source) -> Span | None:
    _, offsets = folded(text)
    if start < end <= len(offsets):
        finish = offsets[end] if end < len(offsets) else len(text)
        return Span(source=source, start=offsets[start], end=finish)
    return None


def seconds(match: re.Match[str]) -> int | None:
    hour, minute = int(match[1]), int(match[2])
    if period := match[3]:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if period == "p" else 0)
    return hour * 3600 + minute * 60 if hour <= 47 else None


def durations(value: str) -> list[tuple[int, int, int]]:
    result: list[tuple[int, int, int]] = []
    for match in DURATION.finditer(value):
        unit = match[2]
        multiplier = (
            3600
            if unit.startswith(("h", "saat"))
            else 60
            if unit.startswith(("m", "dakika"))
            else 1
        )
        amount = int(match[1]) * multiplier
        if result and re.fullmatch(r"\s*(?:and|ve)?\s*", value[result[-1][2] : match.start()]):
            previous, start, _ = result.pop()
            amount += previous
        else:
            start = match.start()
        result.append((amount, start, match.end()))
    return result


def targets(text: str, schedule: Schedule, day: date, trip: bool, source: Source) -> list[Fact]:
    explicit: list[Fact] = []
    for match in IDENTIFIER.finditer(text):
        key = match[0]
        if trip and key in schedule.trips and schedule.runs(schedule.trips[key].service, day):
            explicit.append(
                Fact(
                    slot="target",
                    value=key,
                    span=Span(
                        source=source,
                        start=match.start(),
                        end=match.end(),
                    ),
                )
            )
        if not trip and key in schedule.stops:
            explicit.append(
                Fact(
                    slot="target",
                    value=key,
                    span=Span(
                        source=source,
                        start=match.start(),
                        end=match.end(),
                    ),
                )
            )
    if trip:
        return explicit
    if explicit:
        mentioned = stop_candidates(
            IDENTIFIER.sub(lambda match: " " * len(match[0]), text), schedule
        )
        if mentioned and not any(item.value in mentioned for item in explicit):
            return explicit + targets(
                IDENTIFIER.sub(lambda match: " " * len(match[0]), text),
                schedule,
                day,
                False,
                source,
            )
        return explicit
    value, _ = folded(text)
    keys = stop_candidates(text, schedule)
    if not keys:
        # Independently named stops separated by a disjunction remain alternatives.
        if not re.search(r"\b(?:or|veya|ya da|and|ve)\b", value):
            return []
        keys = tuple(
            sorted(
                {
                    key
                    for part in re.split(r"\b(?:or|veya|ya da|and|ve)\b", value)
                    for key in stop_candidates(part, schedule)
                }
            )
        )
    found: list[Fact] = []
    for key in keys:
        name = normalize(schedule.stops[key].name)
        aliases = (name, name.split()[0]) if name.startswith("konak ") else (name,)
        for alias in aliases:
            match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", value)
            if match:
                found.append(fact("target", key, text, match.start(), match.end(), source))
                break
    return found


def unique(facts: Iterable[Fact]) -> tuple[Fact, ...]:
    return tuple({(item.slot, item.value): item for item in facts}.values())


def extract(
    text: str,
    schedule: Schedule,
    day: date,
    proposal: Extraction | None = None,
) -> tuple[tuple[Fact, ...], tuple[str, ...]]:
    value, offsets = folded(text)
    if re.search(r"\b(?:utc|gmt|zulu)\b", value):
        return (), ("unsupported_timezone",)
    dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", value))
    if UNCERTAIN.search(value) or dates - {day.isoformat()}:
        return (), ("uncertain_or_wrong_service_date",)
    kinds = [
        fact("kind", kind, text, match.start(), match.end(), "notice")
        for kind, pattern in ACTIONS.items()
        if (match := pattern.search(value))
    ]
    if proposal and not kinds:
        # A quoted phrase can enable a supported indirect construction. Check the full text
        # for competing event meanings and resolve offsets on the server.
        indirect = [
            (kind, match) for kind, pattern in INDIRECT.items() for match in pattern.finditer(value)
        ]
        for kind, match in indirect:
            fragment = text[offsets[match.start()] : offsets[match.end() - 1] + 1]
            if any(quote.slot == "kind" and quote.quote == fragment for quote in proposal.quotes):
                if len({entry[0] for entry in indirect}) == 1:
                    kinds.append(fact("kind", kind, text, match.start(), match.end(), "notice"))
    ids = {match[0] for match in IDENTIFIER.finditer(text)}
    if ids - schedule.stops.keys() - schedule.trips.keys():
        return (), ("catalogue_miss",)
    want_trip = any(item.value != "stop_closure" for item in kinds) or bool(
        ids & schedule.trips.keys()
    )
    want_stop = not kinds or any(item.value == "stop_closure" for item in kinds)
    facts = kinds[:]
    if want_trip:
        facts.extend(targets(text, schedule, day, True, "notice"))
    if want_stop:
        stops = targets(text, schedule, day, False, "notice")
        if (
            len({item.value for item in stops}) > 1
            and not stop_candidates(text, schedule)
            and not re.search(r"\b(?:or|veya|ya da)\b", value)
        ):
            return (), ("conflicting_targets",)
        facts.extend(stops)
    times = list(TIME.finditer(value))
    if len(times) == 1:
        previous = value[: times[0].start()].strip()
        slot: Slot = "end" if re.search(r"\b(?:until|to|kadar)\s*$", previous) else "start"
        if (instant := seconds(times[0])) is not None:
            facts.append(fact(slot, instant, text, times[0].start(), times[0].end(), "notice"))
    elif len(times) == 2:
        separator = value[times[0].end() : times[1].start()]
        if not re.fullmatch(r"\s*(?:to|until|and|ile|ve|[-\u2013\u2014])\s*", separator):
            if any(item.value == "stop_closure" for item in kinds):
                return (), ("unbound_times",)
        for field, match in zip(("start", "end"), times, strict=True):
            if (instant := seconds(match)) is not None:
                slot = "start" if field == "start" else "end"
                facts.append(fact(slot, instant, text, match.start(), match.end(), "notice"))
    elif times:
        return (), ("conflicting_times",)
    facts.extend(
        fact("delay", amount, text, start, end, "notice")
        for amount, start, end in durations(value)
        if 0 < amount <= 43200
    )
    return unique(facts), ()


def slot_facts(facts: tuple[Fact, ...], slot: Slot) -> tuple[Fact, ...]:
    return tuple(item for item in facts if item.slot == slot)


def parse_incident(
    values: dict[Slot, str | int], schedule: Schedule, day: date
) -> Disruption | None:
    kind, target = values["kind"], values["target"]
    if not isinstance(target, str):
        return None
    if kind == "stop_closure" and target in schedule.stops:
        start, end = values.get("start"), values.get("end")
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < end < 172800:
            return StopClosure(stop=target, start=start, end=end)
    if target in schedule.trips and schedule.runs(schedule.trips[target].service, day):
        if kind == "trip_cancellation":
            return TripCancellation(trip=target, service_date=day)
        delay = values.get("delay")
        if kind == "trip_delay" and isinstance(delay, int) and 0 < delay <= 43200:
            return TripDelay(trip=target, service_date=day, seconds=delay)
    return None


def hypotheses(
    facts: tuple[Fact, ...],
    schedule: Schedule,
    day: date,
) -> tuple[tuple[Hypothesis, ...], bool]:
    unique_events: dict[str, Hypothesis] = {}
    for kind in slot_facts(facts, "kind"):
        for fields in product(*(slot_facts(facts, slot) for slot in REQUIREMENTS[str(kind.value)])):
            evidence = (kind, *fields)
            event = parse_incident({item.slot: item.value for item in evidence}, schedule, day)
            if event is None:
                continue
            serialized = event.model_dump_json()
            if serialized not in unique_events:
                identifier = hashlib.sha256(serialized.encode()).hexdigest()[:16]
                unique_events[serialized] = Hypothesis(
                    id=identifier, incident=event, facts=evidence
                )
            if len(unique_events) > MAX_HYPOTHESES:
                return (), True
    return tuple(unique_events.values()), False


def label(item: Fact, schedule: Schedule) -> str:
    if item.slot == "target" and str(item.value) in schedule.stops:
        stop = schedule.stops[str(item.value)]
        mode = "Metro" if stop.id.startswith("metro:") else "Tram"
        return f"{stop.name} ({mode})"
    if item.slot in {"start", "end"} and isinstance(item.value, int):
        return f"{item.value // 3600:02d}:{item.value // 60 % 60:02d}"
    if item.slot == "delay":
        return f"{item.value} seconds"
    return str(item.value).replace("_", " ")


def residual(group: list[Impact]) -> tuple[int, int]:
    meetings = [entry.preview.meeting for entry in group if entry.preview is not None]
    return int(len({entry.status for entry in group}) > 1), (
        max(meetings) - min(meetings) if meetings else 0
    )


def decide(
    facts: tuple[Fact, ...],
    reasons: tuple[str, ...],
    schedule: Schedule,
    day: date,
    evaluate: Evaluate,
    version: int,
    *,
    answered: bool = False,
    strategy: str = "impact",
) -> Intake:
    complete, overflow = hypotheses(facts, schedule, day)
    if overflow or reasons:
        return Intake(action="abstain", facts=facts, reasons=reasons or ("too_many_hypotheses",))
    kinds = slot_facts(facts, "kind")
    required: set[Slot] = {"kind", "target"}
    for kind in kinds:
        required.update(REQUIREMENTS[str(kind.value)])
    open_slots: list[Slot] = [
        slot for slot in ORDER if slot in required and len(slot_facts(facts, slot)) != 1
    ]
    if len(complete) == 1 and not open_slots:
        return Intake(action="apply", facts=facts, selected=complete[0])
    if answered:
        return Intake(action="abstain", facts=facts, reasons=("unresolved_after_answer",))

    impacts: list[Impact] = []
    for hypothesis in complete:
        status, preview = evaluate(hypothesis.incident)
        impacts.append(Impact(hypothesis=hypothesis, status=status, preview=preview))
    if not open_slots:
        return Intake(action="abstain", facts=facts, reasons=("invalid_event",))

    def remaining(slot: Slot) -> tuple[int, int, int]:
        partitions: dict[str | int | None, list[Impact]] = {}
        for impact in impacts:
            value = next(
                (item.value for item in impact.hypothesis.facts if item.slot == slot), None
            )
            partitions.setdefault(value, []).append(impact)
        ambiguity, spread = max((residual(group) for group in partitions.values()), default=(0, 0))
        return ambiguity, spread, ORDER.index(slot)

    slot = min(open_slots, key=remaining) if impacts and strategy == "impact" else open_slots[0]
    options = tuple(
        Option(id=f"option-{index}", value=item.value, label=label(item, schedule))
        for index, item in enumerate(slot_facts(facts, slot)[:MAX_OPTIONS], start=1)
    )
    return Intake(
        action="ask",
        facts=facts,
        impacts=tuple(impacts),
        question=Question(
            id=f"q{version}-{slot}",
            slot=slot,
            prompt=PROMPTS[slot],
            options=options,
        ),
    )


def answer_facts(
    intake: Intake,
    answer: str,
    option_id: str | None,
    schedule: Schedule,
    day: date,
) -> tuple[Fact, ...]:
    question = intake.question
    if question is None:
        return ()
    slot = question.slot
    rest = tuple(item for item in intake.facts if item.slot != slot)
    allowed = {option.value for option in question.options}

    def resolved(choice: Fact) -> tuple[Fact, ...]:
        return (*rest, choice) if not allowed or choice.value in allowed else ()

    if option_id is not None:
        option = next((item for item in question.options if item.id == option_id), None)
        if option is None:
            return ()
        choice = next(
            item for item in intake.facts if item.slot == slot and item.value == option.value
        )
        return resolved(choice)
    value, _ = folded(answer)
    if UNCERTAIN.search(value) or normalize(answer.strip()) in {"bilmiyorum", "unknown", "idk"}:
        return ()
    if slot == "target":
        choices = unique(
            targets(answer, schedule, day, True, "answer")
            + targets(answer, schedule, day, False, "answer")
        )
        return resolved(choices[0]) if len(choices) == 1 else ()
    if slot in {"start", "end"}:
        matches = list(TIME.finditer(value))
        if len(matches) == 1 and (time := seconds(matches[0])) is not None:
            match = matches[0]
            return resolved(fact(slot, time, answer, match.start(), match.end(), "answer"))
    if slot == "delay":
        amounts = durations(value)
        if len(amounts) == 1:
            amount, start, end = amounts[0]
            return resolved(fact(slot, amount, answer, start, end, "answer"))
    if slot == "kind":
        fields, _ = extract(answer, schedule, day)
        choices = slot_facts(fields, "kind")
        if len(choices) == 1 and (source := choices[0].span):
            choice = choices[0].model_copy(
                update={"span": source.model_copy(update={"source": "answer"})}
            )
            return resolved(choice)
    return ()
