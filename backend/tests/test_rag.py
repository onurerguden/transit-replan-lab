from pathlib import Path

import pytest
from experiments.bench_v3 import audit, catalogue, generate
from finetune import rag

ROOT = Path("data/bench/v3")
STOPS, _, _ = catalogue.load()


@pytest.fixture(scope="module")
def index() -> rag.Index:
    return rag.build()


def test_retrieval_is_deterministic(index: rag.Index) -> None:
    text = "Update: Sanayi metro station remains closed 12:59-13:24."
    assert index.retrieve(text) == rag.build().retrieve(text)


def test_a_report_never_retrieves_its_own_template(index: rag.Index) -> None:
    for report in generate.read(ROOT / "train.jsonl")[:200]:
        template = audit.mask(report.text, list(STOPS.values()))
        assert all(item.template != template for item in index.retrieve(report.text))


def test_only_train_reports_are_indexed(index: rag.Index) -> None:
    train = {audit.mask(r.text, list(STOPS.values())) for r in generate.read(ROOT / "train.jsonl")}
    assert {item.template for item in index.items} <= train
    for split in ("dev", "calibration", "test"):
        held = {
            audit.mask(r.text, list(STOPS.values())) for r in generate.read(ROOT / f"{split}.jsonl")
        }
        assert not held & {item.template for item in index.items}


def test_examples_differ_in_reply_when_the_bank_allows_it(index: rag.Index) -> None:
    examples = index.retrieve(
        "Not: Üçyol metro istasyonu 10:30'dan 11:00'e kadar kapalı değildir.", 4
    )
    assert len(examples) == 4
    assert len({item.reply for item in examples}) > 1
