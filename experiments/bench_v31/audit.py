# pyright: basic
"""Prove the v3.1 splits are disjoint before any model reads the test split.

The v3 checks apply unchanged: part, exact text, masked template and stop ownership are disjoint,
and no test predicate is in the production lexicon. v3.1 adds phrase-level checks. No predicate,
negation or hedge phrase of the test split equals, contains or sits inside a phrase of another
split, and the sealed parts file is the one the manifest recorded.
"""

from trl.notice import normalize

from experiments.bench_v3 import audit as base
from experiments.bench_v3.generate import Report
from experiments.bench_v31 import banks

# Event wording is under test. Time connectives are shared on purpose, see banks.UNTIL.
PHRASE_TABLES = ("CLOSED", "NEGATED", "HEDGED")
CONTAINMENT = PHRASE_TABLES


def parts() -> dict[str, str]:
    result = {item[0]: item[1] for item in banks.FRAMES}
    for name in banks.TABLES:
        for lang in ("en", "tr"):
            result.update({row[0]: row[1] for row in banks.table(name, lang)})
    return result


def phrases() -> dict[str, dict[str, set[str]]]:
    """Normalized phrase text per split for each phrase table."""
    result: dict[str, dict[str, set[str]]] = {}
    for name in PHRASE_TABLES:
        for lang in ("en", "tr"):
            for row in banks.table(name, lang):
                result.setdefault(name, {}).setdefault(str(row[1]), set()).add(
                    normalize(str(row[2]).replace("{a}", "").replace("{b}", "").strip())
                )
    return result


def phrase_problems() -> list[str]:
    problems: list[str] = []
    for name, per_split in phrases().items():
        for split, items in per_split.items():
            for other, others in per_split.items():
                if split >= other:
                    continue
                for first in items:
                    for second in others:
                        nested = (
                            name in CONTAINMENT
                            and "test" in (split, other)
                            and (first in second or second in first)
                        )
                        if first and second and (first == second or nested):
                            problems.append(
                                f"{name}: {first!r} ({split}) overlaps {second!r} ({other})."
                            )
    return problems


def audit(data: dict[str, list[Report]], stops: dict[str, str]) -> list[str]:
    original = base.generate_parts
    base.generate_parts = parts
    try:
        problems = base.audit(data, stops)
    finally:
        base.generate_parts = original
    return list(dict.fromkeys([*problems, *phrase_problems()]))
