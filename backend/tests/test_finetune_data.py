from pathlib import Path

from finetune.vnext_data import audit_splits, build


def test_vnext_corpus_is_reproducible_and_event_disjoint(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    build(first)
    build(second)
    for name in ("train.jsonl", "valid.jsonl", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert audit_splits(first) == {
        "exact_overlap": 0,
        "event_overlap": 0,
        "family_language_counts": {
            split: {
                f"{kind}/{language}": count
                for kind in ("stop_closure", "trip_delay", "trip_cancellation")
                for language in ("tr", "en")
            }
            for split, count in (("train", 60), ("valid", 10))
        },
    }
    sample = (first / "train.jsonl").read_text().splitlines()[0]
    (first / "valid.jsonl").write_text(sample + "\n")
    audit = audit_splits(first)
    assert audit["exact_overlap"] == audit["event_overlap"] == 1
