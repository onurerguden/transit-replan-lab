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
    trip_ids = re.findall(r"\b(?:metro|tram):[a-zA-Z0-9_-]+", text)
    if len(trip_ids) == 1 and trip_ids[0] in schedule.trips:
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
    explicit = [key for key in schedule.stops if re.search(rf"\b{re.escape(key)}\b", value)]
    named = [
        (len(name), stop.id)
        for stop in schedule.stops.values()
        if re.search(rf"(?<!\w){re.escape(name := normalize(stop.name))}(?!\w)", value)
    ]
    longest = max((length for length, _ in named), default=0)
    stops = explicit or [key for length, key in named if length == longest]
    if len(stops) > 1:
        for mode in ("metro", "tram"):
            if mode in value:
                stops = [key for key in stops if key.startswith(f"{mode}:")]
                break
    if len(stops) != 1 or (stops[0] == "metro:2" and "metro" not in value):
        return None
    return StopClosure(stop=stops[0], start=start, end=end)
