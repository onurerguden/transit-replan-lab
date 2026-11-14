"""Shared schedule, disruption, itinerary, and negotiation contracts."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Second = Annotated[int, Field(ge=0)]
PositiveSecond = Annotated[int, Field(gt=0)]
Rider = Literal["a", "b"]
Architecture = Literal["rules", "single", "three", "five"]
Status = Literal[
    "ready",
    "planning",
    "clarification",
    "abstained",
    "verified",
    "no_agreement",
    "infeasible",
    "search_incomplete",
    "model_error",
    "system_error",
    "verification_failed",
]


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Stop(Record):
    id: str
    name: str
    longitude: float
    latitude: float
    accessible: bool | None = None


class StopTime(Record):
    stop: str
    arrival: Second
    departure: Second
    pickup: bool = True
    dropoff: bool = True


class Trip(Record):
    id: str
    route: str
    service: str
    calls: tuple[StopTime, ...]
    accessible: bool | None = None


class Transfer(Record):
    origin: str
    destination: str
    duration: PositiveSecond
    accessible: bool | None = None


class StopClosure(Record):
    kind: Literal["stop_closure"] = "stop_closure"
    stop: str
    start: Second
    end: PositiveSecond

    @model_validator(mode="after")
    def valid_interval(self) -> "StopClosure":
        if self.end <= self.start:
            raise ValueError("Closure end must follow its start.")
        return self


class TripCancellation(Record):
    kind: Literal["trip_cancellation"] = "trip_cancellation"
    trip: str
    service_date: date


class TripDelay(Record):
    kind: Literal["trip_delay"] = "trip_delay"
    trip: str
    service_date: date
    seconds: Annotated[int, Field(gt=0, le=43200)]


Disruption = Annotated[StopClosure | TripCancellation | TripDelay, Field(discriminator="kind")]


class Walk(Record):
    kind: Literal["walk"] = "walk"
    origin: str
    destination: str
    departure: Second
    arrival: Second


class Ride(Record):
    kind: Literal["ride"] = "ride"
    origin: str
    destination: str
    departure: Second
    arrival: Second
    trip: str
    service_date: date
    board_index: Annotated[int, Field(ge=0)]
    alight_index: Annotated[int, Field(gt=0)]


Leg = Annotated[Ride | Walk, Field(discriminator="kind")]


class Itinerary(Record):
    origin: str
    destination: str
    start: Second
    arrival: Second
    legs: tuple[Leg, ...]


class Constraint(Record):
    stop: str
    ready: Second
    wait_limit: Second
    travel_limit: PositiveSecond = 7200
    walk_limit: Second = 1200
    transfer_limit: Annotated[int, Field(ge=0, le=5)] = 2
    accessible_only: bool = False


class Scenario(Record):
    id: str
    service_date: date
    a: Constraint
    b: Constraint
    destinations: Annotated[tuple[str, ...], Field(min_length=1, max_length=2)]
    meeting_start: Second
    meeting_end: PositiveSecond
    incident: Disruption
    notice: str
    completed_a: tuple[Leg, ...] = ()
    completed_b: tuple[Leg, ...] = ()

    @model_validator(mode="after")
    def valid_window(self) -> "Scenario":
        if self.meeting_start > self.meeting_end or len(set(self.destinations)) != len(
            self.destinations
        ):
            raise ValueError("Specify an ordered window and distinct destinations.")
        for constraint, prefix in ((self.a, self.completed_a), (self.b, self.completed_b)):
            if prefix and (
                prefix[-1].destination != constraint.stop or prefix[-1].arrival > constraint.ready
            ):
                raise ValueError("Completed legs must end at the rider's replanning stop.")
        return self


class Offer(Record):
    id: str
    version: Annotated[int, Field(ge=0)]
    a: Itinerary
    b: Itinerary
    meeting: Second


class Vote(Record):
    rider: Rider
    offer_id: str
    version: Annotated[int, Field(ge=0)]
    accepted: bool
