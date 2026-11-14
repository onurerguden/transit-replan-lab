# pyright: basic
"""Stops and trips the benchmark may talk about: unambiguous names and trips that run."""

from datetime import date

from trl.gtfs import Schedule, load_schedule
from trl.notice import normalize
from trl.scenarios import load_scenario


def unambiguous_stops(schedule: Schedule) -> dict[str, str]:
    names = {stop.id: stop.name for stop in schedule.stops.values()}
    folded = {key: normalize(name) for key, name in names.items()}
    result: dict[str, str] = {}
    for key, value in folded.items():
        clashes = [
            other
            for other, text in folded.items()
            if other != key
            and (
                text == value
                or text.startswith(value + " ")
                or value.startswith(text + " ")
            )
        ]
        if not clashes:
            result[key] = names[key]
    return result


def active_trips(schedule: Schedule, day: date) -> list[str]:
    return sorted(
        trip.id for trip in schedule.trips.values() if schedule.runs(trip.service, day)
    )


def load() -> tuple[dict[str, str], list[str], date]:
    schedule = load_schedule()
    day = load_scenario().service_date
    return unambiguous_stops(schedule), active_trips(schedule, day), day
