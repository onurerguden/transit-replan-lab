from pathlib import Path

import pytest
from experiments.report import Row
from experiments.runner import Condition, lock_results, recover_rows
from pydantic import ValidationError

from trl.agents import PROMPT_VERSION


def row() -> Row:
    return Row(
        split="dev",
        case="demo",
        family="interchange",
        language="en",
        arm="five",
        status="verified",
        oracle="feasible",
        incident_correct=True,
        outcome_correct=True,
        success=True,
        hard_violation=False,
        late_s=0,
        delay_s=0,
        calls=7,
        input_tokens=100,
        output_tokens=20,
        elapsed_ms=300,
        model_digest="base",
        operator_digest="operator",
        gtfs={"metro": "metro"},
        prompt_version=PROMPT_VERSION,
        commit="revision",
        source_diff="patch",
        execution="ollama",
        seed=42,
        counteroffers=True,
    )


def test_results_keep_completed_rows_and_remove_only_torn_suffix(tmp_path: Path) -> None:
    path = tmp_path / "dev.jsonl"
    saved = (row().model_dump_json() + "\n").encode()
    path.write_bytes(saved + b'{"case":"interrupted"')
    assert recover_rows(path) == [row()]
    assert path.read_bytes() == saved

    invalid = saved + b'{"case":"corrupted"}\n'
    path.write_bytes(invalid)
    with pytest.raises(ValidationError):
        recover_rows(path)
    assert path.read_bytes() == invalid


def test_results_disallow_duplicate_pairs(tmp_path: Path) -> None:
    path = tmp_path / "dev.jsonl"
    path.write_text((row().model_dump_json() + "\n") * 2)
    with pytest.raises(SystemExit, match="duplicate"):
        recover_rows(path)


def test_output_lock_excludes_concurrent_writers(tmp_path: Path) -> None:
    path = tmp_path / "dev.lock"
    with lock_results(path), pytest.raises(SystemExit, match="already writing"):
        with lock_results(path):
            pytest.fail("Acquired a lock already held by the evaluator.")
    with lock_results(path):
        assert path.exists()


def test_resume_validates_both_digests_and_source_identity() -> None:
    result = row()
    condition = Condition("revision", "patch", "ollama", "base", "operator", result.gtfs)
    assert condition.accepts(result, "dev")
    for field, value in (
        ("model_digest", "other-base"),
        ("operator_digest", None),
        ("execution", "replay"),
        ("source_diff", "other-patch"),
    ):
        assert not condition.accepts(result.model_copy(update={field: value}), "dev")
    assert not condition.accepts(result, "locked")
