import json

from trl.feeds import network_health
from trl.gtfs import DATA_ROOT
from trl.scenarios import load_scenario


def test_committed_health_report_matches_the_pinned_archives() -> None:
    report = network_health(DATA_ROOT / "gtfs", load_scenario().service_date)
    committed = json.loads((DATA_ROOT / "gtfs" / "health.json").read_text())
    assert json.loads(report.model_dump_json()) == committed
    status = {feed.id: feed.status for feed in report.feeds}
    assert status == {
        "metro": "ok",
        "tram": "ok",
        "bus": "projected_calendar",
        "izban": "projected_calendar",
        "ferry": "unavailable",
    }
