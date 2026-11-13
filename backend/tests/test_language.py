"""Round trips and soundness properties for the time grammar and the evidence gate."""

import re
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from trl.gtfs import load_schedule
from trl.intake import decide, extract
from trl.language.normalize import normalize
from trl.language.timeexpr import parse
from trl.scenarios import load_scenario
from trl.vnext import Extraction, ExtractionQuote

DAY = date(2026, 10, 21)
SCHEDULE = load_schedule()
SERVICE_DAY = load_scenario().service_date


def clock_formats(seconds: int) -> list[str]:
    hour, minute = seconds // 3600, seconds // 60 % 60
    formats = [f"{hour:02d}:{minute:02d}", f"{hour}:{minute:02d}"]
    if hour < 24:
        formats.append(f"{hour:02d}.{minute:02d}")
    return formats


@given(st.integers(0, 47 * 3600 + 59 * 60).filter(lambda value: value % 60 == 0))
@settings(max_examples=300, deadline=None)
def test_every_clock_round_trips_in_every_format(seconds: int) -> None:
    for text in clock_formats(seconds):
        parsed = parse(normalize(f"closed from {text}"), DAY)
        assert not parsed.issues and parsed.start and parsed.start.seconds == seconds, text


@given(
    st.integers(0, 22 * 3600).filter(lambda v: v % 60 == 0),
    st.integers(1, 10_000).map(lambda v: v * 60),
)
@settings(max_examples=200, deadline=None)
def test_ranges_bind_in_either_language_and_order(start: int, length: int) -> None:
    end = start + length
    if end >= 47 * 3600:
        return
    a, b = clock_formats(start)[0], clock_formats(end)[0]
    for text in (
        f"closed from {a} to {b}",
        f"closed until {b} from {a}",
        f"{a}'ten {b}'a kadar kapali",
        f"{b}'a kadar {a}'ten itibaren kapali",
        f"{a} ile {b} arasinda kapali",
    ):
        parsed = parse(normalize(text), DAY)
        assert not parsed.issues, text
        assert parsed.start and parsed.end, text
        assert (parsed.start.seconds, parsed.end.seconds) == (start, end), text


@pytest.mark.parametrize("suffix", ["10'a", "6'ya", "8'e", "4'e"])
def test_turkish_suffix_allomorphs_mark_an_end(suffix: str) -> None:
    hour = int(suffix.split("'")[0])
    parsed = parse(normalize(f"saat {suffix} kadar kapali"), DAY)
    assert parsed.end and parsed.end.seconds == hour * 3600 and parsed.start is None


@given(st.sampled_from(["+03:00", "+0300", "TRT", "UTC+3", "GMT+3"]))
def test_the_local_zone_changes_nothing(zone: str) -> None:
    parsed = parse(normalize(f"closed from 08:24 {zone} to 10:00"), DAY)
    assert not parsed.issues and parsed.start and parsed.start.seconds == 30240


@given(st.sampled_from(["UTC", "GMT", "Z", "+01:00", "-05:00", "GMT+1", "UTC-4"]))
def test_another_zone_is_never_read_silently(zone: str) -> None:
    parsed = parse(normalize(f"closed from 08:24 {zone} to 10:00"), DAY)
    assert "unsupported_timezone" in parsed.issues


@given(
    st.dates(date(2025, 1, 1), date(2028, 12, 31)).filter(lambda value: value != DAY),
    st.sampled_from(["{y}-{m:02d}-{d:02d}", "{d:02d}.{m:02d}.{y}", "{y}-{m:02d}-{d:02d}T08:24:00"]),
)
@settings(max_examples=150, deadline=None)
def test_another_day_is_never_applied(other: date, pattern: str) -> None:
    label = pattern.format(y=other.year, m=other.month, d=other.day)
    text = f"Konak İskele tram stop is closed from 08:24 to 10:00 on {label}."
    facts, reasons = extract(text, SCHEDULE, DAY)
    assert reasons and not facts


@given(st.sampled_from(["tomorrow", "yesterday", "yarin", "next Friday", "gelecek hafta"]))
def test_relative_days_are_never_applied(word: str) -> None:
    text = f"Konak İskele tram stop is closed from 08:24 to 10:00 {word}."
    assert extract(text, SCHEDULE, DAY)[1]


@given(st.sampled_from(["not", "never", "n't", "maybe", "might be", "if"]))
def test_negation_or_hedging_in_the_event_clause_never_applies(word: str) -> None:
    text = f"Konak İskele tram stop {word} closed from 08:24 to 10:00."
    facts, reasons = extract(text, SCHEDULE, DAY)
    decision = decide(facts, reasons, SCHEDULE, DAY, lambda _: ("infeasible", None), 1)
    assert decision.action != "apply"


@given(st.sampled_from(["(no lifts)", "No parking is available.", "Do not use the lift."]))
def test_negation_elsewhere_does_not_block_the_event(note: str) -> None:
    text = f"Konak İskele tram stop is closed from 08:24 to 10:00. {note}"
    decision = decide(
        *extract(text, SCHEDULE, DAY), SCHEDULE, DAY, lambda _: ("infeasible", None), 1
    )
    assert decision.action == "apply"


def quote(text: str, kind: str = "stop_closure") -> Extraction:
    return Extraction(
        quotes=(ExtractionQuote.model_validate({"slot": "kind", "quote": text, "kind": kind}),)
    )


@given(st.text(min_size=1, max_size=40), st.sampled_from(["stop_closure", "trip_delay"]))
@settings(max_examples=200, deadline=None)
def test_a_fabricated_quote_never_creates_an_incident(fabricated: str, kind: str) -> None:
    text = "Konak İskele tram stop is affected from 08:24 to 10:00."
    facts, _ = extract(text, SCHEDULE, DAY, quote(fabricated, kind))
    spoken = normalize(fabricated).strip()
    if len(spoken) < 4 or not re.search(rf"(?<!\w){re.escape(spoken)}(?!\w)", normalize(text)):
        assert not [item for item in facts if item.slot == "kind"]


@given(st.sampled_from(["suspended", "shuttered", "inaccessible", "blocked"]))
def test_a_verified_quote_without_other_fields_is_not_enough(word: str) -> None:
    text = f"Konak İskele tram stop is {word}."
    facts, reasons = extract(text, SCHEDULE, DAY, quote(word))
    decision = decide(facts, reasons, SCHEDULE, DAY, lambda _: ("infeasible", None), 1)
    assert decision.action != "apply"


def test_a_quote_cannot_come_from_a_restored_clause() -> None:
    text = "Konak İskele tram stop reopened after it was shuttered, from 08:24 to 10:00."
    facts, _ = extract(text, SCHEDULE, DAY, quote("shuttered"))
    assert not [item for item in facts if item.slot == "kind"]


def test_the_service_day_fixture_matches() -> None:
    assert SERVICE_DAY == DAY


@pytest.mark.deep
@given(st.text(max_size=60), st.sampled_from(["stop_closure", "trip_cancellation", "trip_delay"]))
@settings(max_examples=20_000, deadline=None)
def test_gate_soundness_over_adversarial_quotes(fabricated: str, kind: str) -> None:
    """No quote creates an incident unless the text, the parsers and the clause all agree."""
    text = (
        "Konak İskele tram stop is not shuttered; Karataş is reopened. Service runs 08:24 to 10:00."
    )
    facts, reasons = extract(text, SCHEDULE, DAY, quote(fabricated, kind))
    decision = decide(facts, reasons, SCHEDULE, DAY, lambda _: ("infeasible", None), 1)
    assert decision.action != "apply"
