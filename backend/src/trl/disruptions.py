"""Compile immutable disruption overlays for a timetable query."""

from collections import defaultdict
from collections.abc import Iterable, Iterator
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

    def walk_windows(
        self, origin: str, destination: str, start: int, latest: int, duration: int
    ) -> Iterator[tuple[int, int]]:
        """Yield inclusive departure ranges whose full walks avoid closed endpoints."""
        intervals = self.closures.get(origin, []) + self.closures.get(destination, [])
        at = start
        for closed_at, reopened_at in sorted(intervals):
            if at >= reopened_at:
                continue
            end = min(latest, closed_at - duration - 1)
            if at <= end:
                yield at, end
            at = max(at, reopened_at)
            if at > latest:
                return
        if at <= latest:
            yield at, latest

    def last_open_second(self, stop: str, at: int, deadline: int) -> int:
        for start, end in self.closures.get(stop, ()):
            if start <= at < end:
                return at - 1
            if at < start:
                deadline = min(deadline, start - 1)
        return deadline
