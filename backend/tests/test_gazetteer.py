import pytest

from trl.catalogue import load_catalogue
from trl.gtfs import DATA_ROOT
from trl.language.gazetteer import Gazetteer

CATALOGUE = load_catalogue(DATA_ROOT / "gtfs", "full")
GAZETTEER = Gazetteer.build(CATALOGUE)


def stops(text: str) -> list[tuple[str, ...]]:
    return [mention.stops for mention in GAZETTEER.find(text)]


@pytest.mark.parametrize(
    "text",
    [
        "Karataş tram stop is closed.",
        "Karataş'ta tramvay durağı kapalı.",
        "Karataşta tramvay kapalı.",
        "KARATAŞ TRAM kapalı",
    ],
)
def test_a_stop_name_with_case_suffixes_resolves_to_the_tram_stop(text: str) -> None:
    mentions = GAZETTEER.find(text)
    assert [stop for mention in mentions for stop in mention.stops] == ["tram:8"]
    assert mentions[0].exact


def test_spans_point_at_the_original_text() -> None:
    text = "Konak İskele'den kalkış yok"
    mention = GAZETTEER.find(text)[0]
    assert text[mention.start : mention.end] == "Konak İskele'den"
    assert mention.stops == ("tram:7",)


def test_a_partial_name_is_ambiguous_until_a_mode_word_narrows_it() -> None:
    bare = GAZETTEER.find("Konak is closed")[0]
    assert not bare.exact and {"metro:2", "tram:7"} <= set(bare.stops)
    narrowed = GAZETTEER.find("Konak metro station is closed")[0]
    assert narrowed.mode == "metro" and set(narrowed.stops) <= {
        s for s in narrowed.stops if s.startswith("metro:")
    }
    assert "metro:2" in narrowed.stops


def test_two_stops_in_one_report_are_two_mentions() -> None:
    mentions = GAZETTEER.find("Konak İskele and Karataş tram stops are closed")
    assert [mention.stops for mention in mentions] == [("tram:7",), ("tram:8",)]


def test_bus_stops_with_repeated_names_stay_ambiguous() -> None:
    names: dict[str, list[str]] = {}
    for stop in CATALOGUE.values():
        if stop.id.startswith("bus:"):
            names.setdefault(stop.name, []).append(stop.id)
    repeated: str = next(
        name for name, ids in sorted(names.items()) if len(ids) > 1 and len(name) > 6
    )
    mention = GAZETTEER.find(f"{repeated} is closed")[0]
    assert mention.ambiguous and mention.exact


def test_text_without_a_stop_has_no_mentions() -> None:
    assert GAZETTEER.find("Services are running normally today.") == []
