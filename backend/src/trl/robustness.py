"""Re-evaluate fixed offers under a shared, deterministic synthetic delay profile."""

import hashlib
from collections.abc import Mapping
from datetime import timedelta
from random import Random

from trl.disruptions import Occurrence, Overlay
from trl.domain import Itinerary, Leg, Offer, Scenario
from trl.gtfs import DATA_ROOT, Schedule
from trl.routing import transfer_margin
from trl.verify import check_plan
from trl.vnext import Counterfactual, OfferEvidence, RoutePolicy

PROFILE = "synthetic-delay-v1"
SEED = 42
POLICIES: tuple[RoutePolicy, ...] = ("earliest", "robust", "balanced")


def snapshot_id(scenario: Scenario) -> str:
    digest = hashlib.sha256(scenario.service_date.isoformat().encode())
    for name in ("feeds.json", "transfers.json"):
        digest.update((DATA_ROOT / "gtfs" / name).read_bytes())
    return digest.hexdigest()


def worlds(
    schedule: Schedule, scenario: Scenario, overlay: Overlay
) -> tuple[dict[Occurrence, int], ...]:
    rng = Random(SEED)
    routes: dict[str, list[Occurrence]] = {}
    earliest = min(scenario.a.ready, scenario.b.ready)
    for trip in sorted(schedule.trips.values(), key=lambda item: item.id):
        for shift in range(
            (earliest - trip.calls[-1].arrival - 43200) // 86400,
            (scenario.meeting_end - trip.calls[0].departure) // 86400 + 1,
        ):
            day = scenario.service_date + timedelta(days=shift)
            occurrence = trip.id, day
            offset = shift * 86400 + overlay.delays.get(occurrence, 0)
            if (
                trip.calls[0].departure + offset <= scenario.meeting_end
                and trip.calls[-1].arrival + offset >= earliest
                and occurrence not in overlay.cancellations
                and schedule.runs(trip.service, day)
            ):
                routes.setdefault(trip.route, []).append(occurrence)
    occurrences = [occurrence for route in sorted(routes) for occurrence in routes[route]]
    names = sorted(routes)
    cases: list[dict[Occurrence, int]] = []
    for group in range(4):
        for _ in range(32):
            perturbation: dict[Occurrence, int] = {}
            if group in {2, 3} and names:
                route = rng.choice(names)
                perturbation.update(dict.fromkeys(routes[route], rng.choice((120, 240))))
            if group in {1, 3} and occurrences:
                occurrence = rng.choice(occurrences)
                perturbation[occurrence] = perturbation.get(occurrence, 0) + rng.choice(
                    (60, 120, 180)
                )
            cases.append(perturbation)
    return tuple(cases)


def shift_route(route: Itinerary, delays: Mapping[Occurrence, int]) -> tuple[Itinerary, str | None]:
    legs: list[Leg] = []
    at = route.start
    for leg in route.legs:
        delta = (
            max(0, at - leg.departure)
            if leg.kind == "walk"
            else delays.get((leg.trip, leg.service_date), 0)
        )
        depart, arrive = leg.departure + delta, leg.arrival + delta
        if depart < at:
            return route, f"missed_connection:{leg.origin}"
        legs.append(
            leg.model_copy(update={"departure": depart, "arrival": arrive}) if delta else leg
        )
        at = arrive
    return route.model_copy(update={"legs": tuple(legs), "arrival": at}), None


def evaluate(
    schedule: Schedule,
    scenario: Scenario,
    offer: Offer,
    overlay: Overlay,
    delays: Mapping[Occurrence, int],
) -> tuple[int | None, str | None]:
    if not delays:
        error = check_plan(schedule, scenario, offer, overlay)
        return (None, error) if error else (offer.meeting, None)
    a, failed_a = shift_route(offer.a, delays)
    b, failed_b = shift_route(offer.b, delays)
    if failure := failed_a or failed_b:
        return None, failure
    meeting = max(offer.meeting, a.arrival, b.arrival)
    shifted = offer.model_copy(update={"a": a, "b": b, "meeting": meeting})
    shifted_delays = dict(overlay.delays)
    for occurrence, delay in delays.items():
        shifted_delays[occurrence] = shifted_delays.get(occurrence, 0) + delay
    adjusted = Overlay(overlay.closures, overlay.cancellations, shifted_delays)
    error = check_plan(schedule, scenario, shifted, adjusted)
    return (None, error) if error else (meeting, None)


def compare(
    schedule: Schedule,
    scenario: Scenario,
    candidates: tuple[Offer, ...],
    overlay: Overlay,
    initial: Offer | None,
    policy: RoutePolicy,
    *,
    reuse_equivalent: bool = True,
) -> tuple[tuple[Offer, ...], tuple[OfferEvidence, ...]]:
    samples = worlds(schedule, scenario, overlay)
    evidence: dict[str, OfferEvidence] = {}
    for offer in candidates:
        relevant = {
            (leg.trip, leg.service_date)
            for route in (offer.a, offer.b)
            for leg in route.legs
            if leg.kind == "ride"
        }
        successful = 0
        verdicts: dict[tuple[tuple[Occurrence, int], ...], bool] = {}
        for sample in samples:
            signature = tuple(
                sorted((key, delta) for key, delta in sample.items() if key in relevant)
            )
            if not reuse_equivalent or signature not in verdicts:
                verdicts[signature] = (
                    evaluate(schedule, scenario, offer, overlay, dict(signature))[1] is None
                )
            successful += verdicts[signature]
        margins = [item for route in (offer.a, offer.b) if (item := transfer_margin(route.legs))]
        tightest = min(margins, key=lambda item: item[0], default=None)
        what_if = None
        if tightest:
            incoming = tightest[1]
            meeting, failure = evaluate(
                schedule,
                scenario,
                offer,
                overlay,
                {(incoming.trip, incoming.service_date): 120},
            )
            what_if = Counterfactual(trip=incoming.trip, meeting=meeting, failure=failure)
        evidence[offer.id] = OfferEvidence(
            offer_id=offer.id,
            policies=(),
            successful=successful,
            total=len(samples),
            transfer_slack=tightest[0] if tightest else None,
            extra_seconds_a=offer.a.arrival - initial.a.arrival if initial else None,
            extra_seconds_b=offer.b.arrival - initial.b.arrival if initial else None,
            counterfactual=what_if,
        )

    def measures(offer: Offer) -> tuple[int, int, int]:
        item = evidence[offer.id]
        burden = max(
            item.extra_seconds_a
            if item.extra_seconds_a is not None
            else offer.a.arrival - offer.a.start,
            item.extra_seconds_b
            if item.extra_seconds_b is not None
            else offer.b.arrival - offer.b.start,
        )
        return offer.meeting, -item.successful, burden

    scores = {offer.id: measures(offer) for offer in candidates}
    front = tuple(
        offer
        for offer in candidates
        if not any(
            other != scores[offer.id]
            and all(left <= right for left, right in zip(other, scores[offer.id], strict=True))
            for other in scores.values()
        )
    )
    if not front:
        return (), ()
    winners: dict[str, Offer] = {}
    for name in (policy, *(item for item in POLICIES if item != policy)):
        index = POLICIES.index(name)
        winner = min(front, key=lambda offer: (scores[offer.id][index], scores[offer.id], offer.id))
        winners[winner.id] = winner
        item = evidence[winner.id]
        evidence[winner.id] = item.model_copy(update={"policies": (*item.policies, name)})
    return tuple(winners.values()), tuple(evidence[identifier] for identifier in winners)
