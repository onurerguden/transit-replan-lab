"""The timetable view the verifier reads. It is the GTFS loader output, never router state."""

from collections.abc import Mapping
from datetime import date
from typing import Protocol

from trl.domain import Stop, Transfer, Trip


class ReferenceTimetable(Protocol):
    @property
    def stops(self) -> Mapping[str, Stop]: ...

    @property
    def trips(self) -> Mapping[str, Trip]: ...

    @property
    def transfers(self) -> tuple[Transfer, ...]: ...

    def runs(self, service_id: str, day: date) -> bool: ...
