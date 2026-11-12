"""Extract timetable evidence from explicit Turkish and English notices."""

import re
import unicodedata
from datetime import date

from trl.domain import Disruption, StopClosure, TripCancellation, TripDelay
from trl.gtfs import Schedule

CLOCK = re.compile(r"(?<![\d:])(\d{1,2}):([0-5]\d)(?![\d:])")
IDENTIFIER = re.compile(r"(?<![\w:])(?:metro|tram):[\w-]+(?![\w:-])")
MERIDIEM = re.compile(r"(?<![a-z])(?:a\.?m\.?|p\.?m\.?)(?![a-z])")
OTHER_UNITS = re.compile(r"\d\s*(?:hours?|hrs?|seconds?|secs?|saat|saniye)\b")
MINUTES = re.compile(r"(?<![\d.+-])(\d+)\s*(?:minutes?|mins?|dakika)\b")
ACTIONS = {
    "stop_closure": re.compile(r"\b(?:clos(?:ed?|ure|ing)|kapal\w*|kapat\w*)\b"),
    "trip_cancellation": re.compile(r"\b(?:cancel\w*|iptal)\b"),
    "trip_delay": re.compile(r"\b(?:delay\w*|gecik\w*|late|behind schedule)\b"),
}
UNCERTAIN = re.compile(
    r"\b(?:no|not|never|maybe|might|possibly|possible|if|or|tomorrow|yesterday|"
    r"degil|belki|muhtemel\w*|veya|ya da|yarin|dun|edilmedi|kapatilmadi|gecikmiyor)"
    r"\b|\?|n['\u2019]t\b"
)


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold().replace("\u0131", "i"))
    return "".join(char for char in folded if not unicodedata.combining(char))


def rule_notice(text: str, schedule: Schedule, day: date) -> Disruption | None:
    value = normalize(text)
    dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", value))
    if UNCERTAIN.search(value) or dates - {day.isoformat()}:
        return None
    actions = [kind for kind, pattern in ACTIONS.items() if pattern.search(value)]
    identifiers = tuple(dict.fromkeys(IDENTIFIER.findall(text)))
    if actions == ["stop_closure"]:
        stamps = CLOCK.findall(value)
        stops = stop_candidates(value, schedule)
        if (
            len(stamps) != 2
            or len(stops) != 1
            or set(identifiers) - set(stops)
            or MERIDIEM.search(value)
        ):
            return None
        start, end = (int(hour) * 3600 + int(minute) * 60 for hour, minute in stamps)
        if 0 <= start < end <= 172800:
            return StopClosure(stop=stops[0], start=start, end=end)
        return None
    if len(identifiers) != 1 or identifiers[0] not in schedule.trips:
        return None
    trip = identifiers[0]
    if not schedule.runs(schedule.trips[trip].service, day):
        return None
    if actions == ["trip_cancellation"]:
        return TripCancellation(trip=trip, service_date=day)
    minutes = MINUTES.findall(value)
    if (
        actions == ["trip_delay"]
        and len(minutes) == 1
        and not OTHER_UNITS.search(value)
        and 0 < int(minutes[0]) <= 720
    ):
        return TripDelay(trip=trip, service_date=day, seconds=int(minutes[0]) * 60)
    return None


def stop_candidates(text: str, schedule: Schedule) -> tuple[str, ...]:
    value = normalize(text)
    names = {stop.id: normalize(stop.name) for stop in schedule.stops.values()}
    references: dict[tuple[int, int], set[str]] = {}
    for name in set(names.values()):
        for match in re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)", value):
            references[match.span()] = {
                stop for stop, full in names.items() if full == name or full.startswith(name + " ")
            }
    # A name wholly inside a longer name is the same mention.
    spans = list(references)
    groups = [
        references[start, end]
        for start, end in spans
        if not any(
            left <= start and end <= right and (left, right) != (start, end)
            for left, right in spans
        )
    ]
    explicit = set(IDENTIFIER.findall(value)) & names.keys()
    if explicit:
        groups.append(explicit)
    if not groups:
        return ()
    candidates = groups[0].intersection(*groups[1:])
    modes = {
        mode
        for mode, pattern in (("metro", r"\bmetro\b"), ("tram", r"\btram(?:way|vay)?\b"))
        if re.search(pattern, value)
    }
    return tuple(
        stop for stop in sorted(candidates) if not modes or stop.partition(":")[0] in modes
    )
