import csv
import json
from pathlib import Path

from experiments.bench_v3.generate import read
from scripts.export_review_packet import export
from scripts.review_agreement import compare, kappa

SPLIT = Path("data/bench/v3/test.jsonl")


def fill(path: Path, answers: dict[str, tuple[str, str]]) -> None:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["action"], row["event"] = answers.get(row["id"], ("abstain", "none"))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_the_packet_hides_gold_and_the_key_stays_apart(tmp_path: Path) -> None:
    export(SPLIT, 40, 1, tmp_path / "packet", tmp_path / "key" / "key.json")
    text = (tmp_path / "packet" / "packet.csv").read_text(encoding="utf-8")
    header = text.splitlines()[0].split(",")
    assert header[:3] == ["id", "language", "text"]
    assert "test-" not in text and "apply" not in text.split("\n", 1)[1]
    key = json.loads((tmp_path / "key" / "key.json").read_text())
    assert len(key) == 40 and all(value.startswith("test-") for value in key.values())
    assert not (tmp_path / "packet" / "key.json").exists()


def test_a_perfect_annotator_agrees_with_the_gold_and_with_a_copy(tmp_path: Path) -> None:
    export(SPLIT, 40, 1, tmp_path / "packet", tmp_path / "key" / "key.json")
    key = json.loads((tmp_path / "key" / "key.json").read_text())
    gold = {report.id: report for report in read(SPLIT)}
    answers = {
        i: (
            gold[b].action,
            str(gold[b].incidents[0]["kind"]) if gold[b].incidents else "none",
        )
        for i, b in key.items()
    }
    first, second = tmp_path / "a.csv", tmp_path / "b.csv"
    for target in (first, second):
        target.write_text((tmp_path / "packet" / "packet.csv").read_text(encoding="utf-8"))
        fill(target, answers)
    result = compare(first, second, tmp_path / "key" / "key.json", SPLIT)
    assert result["kappa_action"] == 1.0 and result["disagreements_action"] == []
    assert result["first_matches_gold_action"] == 40 == result["second_matches_gold_event"]


def test_kappa_penalizes_agreement_that_chance_would_produce() -> None:
    assert kappa(["a", "a", "b", "b"], ["a", "a", "b", "b"]) == 1.0
    assert kappa(["a", "a", "a", "a"], ["a", "a", "a", "a"]) == 1.0
    assert abs(kappa(["a", "b", "a", "b"], ["a", "a", "b", "b"])) < 1e-9
