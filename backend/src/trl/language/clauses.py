"""Split a report into clauses so negation and hedging apply only where they are written."""

import re
from collections.abc import Iterator

BOUNDARY = re.compile(r"[.;!\n()]|\b(?:but|however|ama|ancak|fakat|whereas)\b")
HEDGE = re.compile(
    r"\b(?:no|not|never|maybe|might|possibly|possible|expected|if|degil|belki|"
    r"muhtemel\w*|olabilir|bekleniyor|edilmedi|kapatilmadi|gecikmiyor)\b|n['’]t\b|\?"
)
# A clause that says service is normal or restored is evidence against a disruption.
ANTI_EVIDENCE = re.compile(
    r"\b(?:normal\w*|reopen\w*|resum\w*|restor\w*|as scheduled|acildi|yeniden hizmet\w*|"
    r"normale don\w*|sorunsuz)\b"
)


def clauses(value: str) -> Iterator[tuple[int, int]]:
    """Yield `(start, end)` spans of the folded text, without the boundary characters."""
    start = 0
    for match in BOUNDARY.finditer(value):
        if match.start() > start:
            yield start, match.start()
        start = match.end()
    if start < len(value):
        yield start, len(value)


def clause_at(value: str, position: int) -> tuple[int, int]:
    for start, end in clauses(value):
        if start <= position < end:
            return start, end
    return position, position + 1


def blocked(value: str, span: tuple[int, int]) -> bool:
    """Whether the clause is negated, hedged, a question or says service is normal."""
    text = value[span[0] : span[1]]
    return bool(HEDGE.search(text) or ANTI_EVIDENCE.search(text))
