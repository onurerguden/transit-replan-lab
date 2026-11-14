import json
from pathlib import Path

from experiments.bench_v3 import catalogue
from experiments.bench_v3.generate import SPLITS
from experiments.bench_v31 import audit, banks, generate

ROOT = Path("data/bench/v31")
STOPS, TRIPS, _ = catalogue.load()


def test_committed_splits_pass_the_audit_and_match_the_freeze() -> None:
    data = {split: generate.read(ROOT / f"{split}.jsonl") for split in SPLITS}
    assert audit.audit(data, STOPS) == []
    frozen = json.loads((ROOT / "FREEZE.json").read_text())
    from experiments.bench_v31.__main__ import CODE, manifest

    assert manifest({s: ROOT / f"{s}.jsonl" for s in SPLITS}, frozen["seed"], CODE) == frozen


def test_generation_is_deterministic() -> None:
    first = generate.build("calibration", STOPS, TRIPS, 7)
    assert first == generate.build("calibration", STOPS, TRIPS, 7)
    assert first != generate.build("calibration", STOPS, TRIPS, 8)


def test_every_quoted_phrase_is_in_its_sentence() -> None:
    for report in generate.build("train", STOPS, TRIPS, 7)[:400]:
        if report.kind_phrase:
            assert report.kind_phrase in report.text, report.text


def test_two_stop_reports_quote_the_plural_phrase() -> None:
    pairs = [r for r in generate.build("train", STOPS, TRIPS, 7) if r.family == "closure_pair"]
    assert pairs
    assert all(r.kind_phrase and r.kind_phrase in r.text for r in pairs)
    english = [r.kind_phrase for r in pairs if r.lang == "en" and r.kind_phrase]
    assert any(phrase.startswith(("are", "have")) or " are " in f" {phrase} " for phrase in english)


def test_every_negated_or_hedged_phrase_is_blocked_by_the_gate() -> None:
    """Split-owned phrases that the clause rules cannot block would teach a false application."""
    from trl.language.clauses import blocked
    from trl.notice import normalize

    for name in ("NEGATED", "HEDGED"):
        for lang in ("en", "tr"):
            for row in banks.table(name, lang):
                value = normalize(f"station {row[2]} today")
                start = value.index(normalize(str(row[2])))
                assert blocked(value, (start, start + len(normalize(str(row[2]))))), row


def test_each_split_owns_parts_in_every_table_it_needs() -> None:
    for split in SPLITS:
        for name in (
            "CLOSED",
            "LEADS",
            "TIME_FORMS",
            "UNTIL",
            "FROM",
            "NEGATED",
            "HEDGED",
            "CALM",
            "NOTES",
            "DATES",
        ):
            for lang in ("en", "tr"):
                assert any(row[1] == split for row in banks.table(name, lang)), (name, lang, split)
    assert {row[1] for row in banks.FRAMES} == set(SPLITS)
