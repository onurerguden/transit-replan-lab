import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest
from experiments.bench_v3 import audit, catalogue, generate, morph_tr, stats
from experiments.bench_v3.generate import SIZES, SPLITS

ROOT = Path("data/bench/v3")
STOPS, TRIPS, DAY = catalogue.load()


def data() -> dict[str, list[generate.Report]]:
    return {split: generate.read(ROOT / f"{split}.jsonl") for split in SPLITS}


def test_committed_splits_pass_the_audit_and_match_the_freeze() -> None:
    assert audit.audit(data(), STOPS) == []
    frozen = json.loads((ROOT / "FREEZE.json").read_text())
    code = [
        Path("experiments/bench_v3") / name
        for name in ("generate.py", "morph_tr.py", "catalogue.py")
    ]
    paths = {split: ROOT / f"{split}.jsonl" for split in SPLITS}
    assert audit.manifest(paths, frozen["seed"], code) == frozen


def test_generation_is_deterministic() -> None:
    first = generate.build("calibration", STOPS, TRIPS, 7)
    again = generate.build("calibration", STOPS, TRIPS, 7)
    assert first == again and len(first) == 2 * SIZES["calibration"]


def test_every_family_is_present_in_every_split() -> None:
    for split, rows in data().items():
        assert {row.family for row in rows} == set(generate.FAMILIES), split


def test_the_audit_catches_a_leaked_part_and_a_leaked_stop() -> None:
    sets = data()
    leaked = sets["test"][0]
    sets["train"][0] = replace(sets["train"][0], parts=(*sets["train"][0].parts, leaked.parts[0]))
    assert any("appears in" in message for message in audit.audit(sets, STOPS))
    sets = data()
    test_stop = next(
        stop for stop, owner in generate.assign_stops(STOPS).items() if owner == "test"
    )
    sets["dev"][0] = replace(sets["dev"][0], stops=(test_stop,))
    assert any("another split" in message for message in audit.audit(sets, STOPS))


def test_test_predicates_are_outside_the_production_lexicon() -> None:
    lexical = [row for row in data()["test"] if row.family in {"closure_range", "closure_pair"}]
    assert lexical and not [m for m in audit.audit(data(), STOPS) if "lexicon" in m]


def test_a_fifth_of_the_stops_are_held_out_for_test() -> None:
    owners = Counter(generate.assign_stops(STOPS).values())
    assert owners["test"] >= len(STOPS) // 6 and set(owners) == set(SPLITS)


@pytest.mark.parametrize(
    ("word", "locative", "ablative", "dative"),
    [
        ("Karataş", "Karataş'ta", "Karataş'tan", "Karataş'a"),
        ("Konak", "Konak'ta", "Konak'tan", "Konak'a"),
        ("Bornova", "Bornova'da", "Bornova'dan", "Bornova'ya"),
        ("Üçyol", "Üçyol'da", "Üçyol'dan", "Üçyol'a"),
        ("Göztepe", "Göztepe'de", "Göztepe'den", "Göztepe'ye"),
    ],
)
def test_turkish_suffixes_follow_harmony_and_assimilation(
    word: str, locative: str, ablative: str, dative: str
) -> None:
    assert morph_tr.locative(word) == locative
    assert morph_tr.ablative(word) == ablative
    assert morph_tr.dative(word) == dative


def test_clock_suffixes_follow_the_spoken_number() -> None:
    assert morph_tr.clock_ablative("07:13") == "07:13'ten"
    assert morph_tr.clock_dative("20:59") == "20:59'a"
    assert morph_tr.clock_dative("17:42") == "17:42'ye"


def test_exact_interval_and_tests_behave() -> None:
    low, high = stats.clopper_pearson(0, 1000)
    assert low == 0.0 and 0.0029 < high < 0.0038
    assert stats.mcnemar_exact(0, 0) == 1.0
    assert stats.mcnemar_exact(0, 10) < 0.01 and stats.mcnemar_exact(5, 5) == 1.0
    assert stats.holm({"a": 0.01, "b": 0.04, "c": 0.5}) == {"a": 0.03, "b": 0.08, "c": 0.5}
    centre, low, high = stats.cluster_bootstrap([1.0, 1.0, 0.0, 1.0], ["a", "a", "b", "c"], 200)
    assert low <= centre <= high
