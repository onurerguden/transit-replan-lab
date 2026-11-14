"""Verify plans against the timetable with semantics written independently of the router."""

from trl.verifier.check import check_itinerary, check_plan, verify_offer
from trl.verifier.semantics import IncidentState

__all__ = ["IncidentState", "check_itinerary", "check_plan", "verify_offer"]
