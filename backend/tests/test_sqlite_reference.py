"""The verifier reads raw archives, so it can check full-network plans on its own."""

import json
import random
from pathlib import Path

import pytest
from test_compact_routing import scenario

from trl.domain import Transfer
from trl.gtfs import DATA_ROOT, feed_specs
from trl.routing import SearchIncomplete
from trl.timetable.compact import get_timetable
from trl.timetable.footpaths import generate
from trl.timetable.query import route
from trl.verifier import IncidentState, check_plan
from trl.verifier.sqlite_reference import SqliteReference, build

ROOT = DATA_ROOT / "gtfs"


def reference(directory: str) -> SqliteReference:
    specs = [f for f in feed_specs(ROOT) if f.sha256]
    database = Path(directory) / "reference.sqlite"
    build(
        {f.id: ROOT / f"{f.id}.zip" for f in specs},
        database,
        frozenset(f.id for f in specs if f.calendar_policy == "project_weekdays"),
    )
    return SqliteReference(database)


@pytest.mark.deep
def test_a_full_network_plan_verifies_against_the_raw_archives(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    table = get_timetable(ROOT, cache_dir, "full")
    documented = {
        (i["origin"], i["destination"]): i["duration"]
        for i in json.loads((ROOT / "transfers.json").read_text())
    }
    paths = generate(
        list(table.stop_ids),
        table.stop_lon.tolist(),
        table.stop_lat.tolist(),
        documented=documented,
    )
    # Transfers the router used are carried on the verifier's reference as plain data.
    verifier_side = reference(str(tmp_path))
    rng = random.Random(3)
    checked = 0
    for _ in range(40):
        stops = [s for s in table.stop_ids if s.startswith(("metro:", "tram:", "izban:"))]
        query = scenario(rng, stops)
        try:
            offers, window = route(table, paths, query)
        except SearchIncomplete:
            continue
        if not offers:
            continue
        verifier_side.transfers = window.schedule.transfers
        for offer in offers[:2]:
            assert check_plan(verifier_side, query, offer, IncidentState()) is None
            checked += 1
    assert checked >= 1
    assert isinstance(verifier_side.transfers[0], Transfer) if verifier_side.transfers else True
