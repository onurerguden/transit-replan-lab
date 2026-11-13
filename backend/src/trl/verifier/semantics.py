"""Interpret disruptions for verification, following docs/semantics/closures.md.

This module deliberately re-implements closure semantics instead of reusing the router's
overlay, so a shared mistake requires two independent implementations to agree.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date

from trl.domain import Disruption

Occurrence = tuple[str, date]


@dataclass(frozen=True)
class IncidentState:
    """Closures are half-open intervals [start, end) in service-day seconds."""

    closures: Mapping[str, list[tuple[int, int]]] = field(
        default_factory=dict[str, list[tuple[int, int]]]
    )
    cancellations: frozenset[Occurrence] | set[Occurrence] = frozenset()
    delays: Mapping[Occurrence, int] = field(default_factory=dict[Occurrence, int])

    @classmethod
    def from_disruptions(cls, incidents: Iterable[Disruption]) -> "IncidentState":
        closures: dict[str, list[tuple[int, int]]] = {}
        cancellations: set[Occurrence] = set()
        delays: dict[Occurrence, int] = {}
        for incident in incidents:
            if incident.kind == "stop_closure":
                closures.setdefault(incident.stop, []).append((incident.start, incident.end))
            elif incident.kind == "trip_cancellation":
                cancellations.add((incident.trip, incident.service_date))
            else:
                key = (incident.trip, incident.service_date)
                delays[key] = delays.get(key, 0) + incident.seconds
        return cls(closures, frozenset(cancellations), delays)

    def occupied_while_closed(self, stop: str, first: int, last: int) -> bool:
        """Whether presence over the closed interval [first, last] meets any closure."""
        if last < first:
            return False
        # [first, last] meets [closed_from, reopens) unless it ends before or starts after it.
        return any(
            not (last < closed_from or first >= reopens)
            for closed_from, reopens in self.closures.get(stop, ())
        )
