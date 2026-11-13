"""Resolve `the 08:15 departure from Konak` to a scheduled trip.

A reference names a stop and a departure time. It resolves only when exactly one trip running
on the service day leaves that stop at that time. Several matches become options for a
question, and none means the report does not identify a trip.
"""

from datetime import date

from trl.gtfs import Schedule
from trl.language import timeexpr
from trl.language.normalize import folded
from trl.notice import stop_candidates

MAX_OPTIONS = 4


def resolve(text: str, schedule: Schedule, day: date) -> list[tuple[str, int, int]]:
    """Return `(trip id, start, end)` for every trip the reference could mean.

    Offsets index into the folded text, which `span_at` maps back to the original.
    """
    value, _ = folded(text)
    stops = set(stop_candidates(text, schedule))
    parsed = timeexpr.parse(value, day)
    if not stops or parsed.issues or len(parsed.clocks) != 1:
        return []
    clock = parsed.clocks[0]
    found: list[tuple[str, int, int]] = []
    for trip in schedule.trips.values():
        for call in trip.calls[:-1]:
            if call.stop in stops and call.pickup and call.departure == clock.seconds:
                if schedule.runs(trip.service, day):
                    found.append((trip.id, clock.start, clock.end))
                break
    return found[: MAX_OPTIONS + 1]
