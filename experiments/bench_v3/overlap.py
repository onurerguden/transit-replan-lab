"""Measure wording overlap between banks and drop near-duplicate training rows.

Texts are masked first (stop names, numbers and identifiers removed) so overlap reflects the
event wording and not the stops or clock times. Containment is exact. Near-duplicate removal
uses MinHash signatures with banded buckets, which keeps the cost linear in the bank size.
"""

import hashlib
import re
from collections.abc import Iterable, Sequence

WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
PERMUTATIONS = 64
BANDS = 16
MASK_64 = (1 << 64) - 1


def shingles(text: str, size: int = 3) -> frozenset[str]:
    """Word n-grams of a masked text. Texts shorter than `size` words give one shingle."""
    words = WORD.findall(text.lower())
    if len(words) <= size:
        return frozenset({" ".join(words)}) if words else frozenset()
    return frozenset(
        " ".join(words[i : i + size]) for i in range(len(words) - size + 1)
    )


def containment(
    left: Iterable[frozenset[str]], right: Iterable[frozenset[str]]
) -> float:
    """Share of `left` shingles that also occur anywhere in `right`."""
    pool: set[str] = set()
    for item in right:
        pool |= item
    own = [s for item in left for s in item]
    return sum(s in pool for s in own) / len(own) if own else 0.0


def _hash(shingle: str, seed: int) -> int:
    digest = hashlib.blake2b(
        shingle.encode(), digest_size=8, salt=seed.to_bytes(8, "big")
    ).digest()
    return int.from_bytes(digest, "big") & MASK_64


def signature(items: frozenset[str]) -> tuple[int, ...]:
    return tuple(min(_hash(s, seed) for s in items) for seed in range(PERMUTATIONS))


def near_duplicates(docs: Sequence[frozenset[str]], threshold: float = 0.8) -> set[int]:
    """Indexes of documents whose estimated Jaccard similarity to an earlier one is high."""
    rows = PERMUTATIONS // BANDS
    buckets: dict[tuple[int, tuple[int, ...]], list[int]] = {}
    signatures = [signature(d) if d else () for d in docs]
    dropped: set[int] = set()
    for number, sig in enumerate(signatures):
        if not sig:
            continue
        candidates: set[int] = set()
        keys = [(band, sig[band * rows : (band + 1) * rows]) for band in range(BANDS)]
        for key in keys:
            candidates.update(buckets.get(key, ()))
        for other in candidates:
            same = sum(a == b for a, b in zip(sig, signatures[other], strict=True))
            if same / PERMUTATIONS >= threshold:
                dropped.add(number)
                break
        if number not in dropped:
            for key in keys:
                buckets.setdefault(key, []).append(number)
    return dropped
