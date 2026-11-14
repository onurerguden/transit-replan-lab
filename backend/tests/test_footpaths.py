import json

from hypothesis import given, settings
from hypothesis import strategies as st

from trl.catalogue import load_catalogue
from trl.gtfs import DATA_ROOT
from trl.timetable.footpaths import FootpathParams, generate

PARAMS = FootpathParams()
points = st.lists(
    st.tuples(st.floats(27.0, 27.02), st.floats(38.40, 38.42)), min_size=2, max_size=40
)


def table(coordinates: list[tuple[float, float]]):
    ids = [f"s{index}" for index in range(len(coordinates))]
    return ids, generate(ids, [c[0] for c in coordinates], [c[1] for c in coordinates])


@given(points)
@settings(max_examples=60, deadline=None)
def test_links_are_symmetric_bounded_and_satisfy_the_triangle_inequality(
    coordinates: list[tuple[float, float]],
) -> None:
    ids, paths = table(coordinates)
    cost = {(a, b): seconds for a in range(len(ids)) for b, seconds in paths.links(a)}
    for (a, b), seconds in cost.items():
        assert PARAMS.buffer_s <= seconds <= PARAMS.max_s
        assert cost[b, a] == seconds
    for (a, b), first in cost.items():
        for (c, d), second in cost.items():
            if b == c and a != d and (a, d) in cost:
                assert cost[a, d] <= first + second


def test_a_distant_pair_has_no_link_and_a_close_pair_does() -> None:
    ids = ["near-a", "near-b", "far"]
    paths = generate(ids, [27.0, 27.001, 27.2], [38.4, 38.4, 38.4])
    assert [dest for dest, _ in paths.links(0)] == [1]
    assert paths.links(2) == []


def test_documented_interchanges_replace_generated_durations() -> None:
    ids = ["a", "b"]
    paths = generate(ids, [27.0, 27.0001], [38.4, 38.4], documented={("a", "b"): 480})
    assert paths.links(0) == [(1, 480)]
    assert paths.links(1)[0][1] < 480


def test_the_real_network_keeps_its_two_documented_interchanges() -> None:
    stops = load_catalogue(DATA_ROOT / "gtfs", "full")
    ids = list(stops)
    documented = {
        (item["origin"], item["destination"]): item["duration"]
        for item in json.loads((DATA_ROOT / "gtfs" / "transfers.json").read_text())
    }
    paths = generate(
        ids,
        [stops[i].longitude for i in ids],
        [stops[i].latitude for i in ids],
        documented=documented,
    )
    index = {name: position for position, name in enumerate(ids)}
    assert dict(paths.links(index["metro:2"]))[index["tram:7"]] == 480
    assert dict(paths.links(index["tram:21"]))[index["metro:17"]] == 480
    assert paths.count > 50_000
    assert all(
        0 < seconds <= max(PARAMS.max_s, 480)
        for destination in [paths.seconds]
        for seconds in destination
    )
