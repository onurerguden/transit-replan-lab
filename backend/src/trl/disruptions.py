"""Compile immutable disruption overlays for a timetable query."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from trl.domain import Disruption

Occurrence = tuple[str, date]


@dataclass(frozen=True)
class Overlay:
    closures: dict[str, list[tuple[int, int]]]
    cancellations: set[Occurrence]
    delays: dict[Occurrence, int]

    @classmethod
    def compile(cls, incidents: Iterable[Disruption]) -> "Overlay":
        closures: dict[str, list[tuple[int, int]]] = defaultdict(list)
        cancellations: set[Occurrence] = set()
        delays: dict[Occurrence, int] = {}
        for incident in incidents:
            if incident.kind == "stop_closure":
                closures[incident.stop].append((incident.start, incident.end))
            elif incident.kind == "trip_cancellation":
                cancellations.add((incident.trip, incident.service_date))
            else:
                delays[incident.trip, incident.service_date] = incident.seconds
        return cls(dict(closures), cancellations, delays)

    def closed(self, stop: str, start: int, end: int | None = None) -> bool:
        last = start if end is None else end
        return any(start < until and last >= since for since, until in self.closures.get(stop, ()))

    def first_open_walk(self, origin: str, destination: str, at: int, duration: int) -> int:
        intervals = self.closures.get(origin, []) + self.closures.get(destination, [])
        for start, end in sorted(intervals):
            if at < end and at + duration >= start:
                at = end
        return at
