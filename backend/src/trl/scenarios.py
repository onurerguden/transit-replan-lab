"""Load bundled synthetic scenarios."""

from trl.domain import Scenario
from trl.gtfs import DATA_ROOT


def load_scenario(name: str = "demo") -> Scenario:
    if name not in {"demo", "infeasible", "resilience"}:
        raise ValueError("Unknown scenario.")
    scenario = Scenario.model_validate_json((DATA_ROOT / "scenarios" / "demo.json").read_bytes())
    if name == "infeasible":
        return scenario.model_copy(update={"id": name, "meeting_end": 33000})
    if name == "resilience":
        return scenario.model_copy(
            update={
                "id": name,
                "notice": "Konak İskele or Karataş tram stop is closed from 08:24 to 10:00.",
            }
        )
    return scenario
