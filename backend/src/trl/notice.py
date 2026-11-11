"""Transparent rule baseline for the supported synthetic notice grammar."""

import re
import unicodedata
from datetime import date

from trl.domain import Disruption, StopClosure, TripCancellation, TripDelay
from trl.gtfs import Schedule


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.casefold().replace("\u0131", "i"))
    return "".join(char for char in folded if not unicodedata.combining(char))


def rule_notice(text: str, schedule: Schedule, day: date) -> Disruption | None:
    value = normalize(text)
    trip_ids = trip_candidates(text, schedule)
    if len(trip_ids) == 1:
        trip = trip_ids[0]
        if re.search(r"cancel|iptal", value):
            return TripCancellation(trip=trip, service_date=day)
        delay = re.search(r"(\d+)\s*(?:minutes?|min\b|dakika)", value)
        if delay and re.search(r"delay|gecik", value) and 0 < int(delay[1]) <= 720:
            return TripDelay(trip=trip, service_date=day, seconds=int(delay[1]) * 60)
    if not re.search(r"clos|kapal|kapat", value):
        return None
    stamps = re.findall(r"\b([0-2]?\d):([0-5]\d)\b", value)
    if len(stamps) != 2:
        return None
    start, end = (int(hour) * 3600 + int(minute) * 60 for hour, minute in stamps)
    if end <= start:
        return None
    stops = stop_candidates(text, schedule)
    if len(stops) != 1:
        return None
    return StopClosure(stop=stops[0], start=start, end=end)


def stop_candidates(text: str, schedule: Schedule) -> tuple[str, ...]:
    value = normalize(text)
    explicit = tuple(key for key in schedule.stops if re.search(rf"\b{re.escape(key)}\b", value))
    if explicit:
        return explicit
    modes = {
        mode
        for mode, pattern in (("metro", r"\bmetro\b"), ("tram", r"\btram(?:way|vay)?\b"))
        if re.search(pattern, value)
    }
    names = {stop.id: normalize(stop.name) for stop in schedule.stops.values()}
    matches = [
        (name, stop)
        for stop, name in names.items()
        if re.search(rf"(?<!\w){re.escape(name)}(?!\w)", value)
    ]
    if not matches:
        return ()
    longest = max(len(name) for name, _ in matches)
    matched_names = {name for name, _ in matches if len(name) == longest}
    return tuple(
        stop
        for stop, name in names.items()
        if (not modes or stop.partition(":")[0] in modes)
        and any(name == match or name.startswith(match + " ") for match in matched_names)
    )


def trip_candidates(text: str, schedule: Schedule) -> tuple[str, ...]:
    return tuple(
        trip
        for trip in re.findall(r"\b(?:metro|tram):[a-zA-Z0-9_-]+", text)
        if trip in schedule.trips
    )
