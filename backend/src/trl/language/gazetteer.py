"""Find stop mentions in free text, including Turkish case suffixes.

Stop names repeat across directions and modes, so a mention maps to a set of stops. A mention
that names only the start of a longer stop name is reported as partial, and a nearby mode word
narrows the set. The gazetteer never picks one stop out of an ambiguous set. The clarification
step does.
"""

import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from trl.domain import Stop
from trl.language.normalize import folded, normalize

WORD = re.compile(r"\w+")
MAX_WORDS = 6
# Case suffixes after a stop name: locative, ablative, dative, accusative, genitive.
SUFFIXES = frozenset(
    "da de ta te dan den tan ten a e ya ye i ı u ü yi yı yu yü in ın un ün nin nın nun nün".split()
) | {normalize(item) for item in "da de ta te dan den tan ten a e ya ye i yi in nin".split()}
MODE_WORDS: dict[str, str] = {
    "metro": "metro",
    "tram": "tram",
    "tramvay": "tram",
    "tramway": "tram",
    "otobus": "bus",
    "bus": "bus",
    "izban": "izban",
    "vapur": "ferry",
    "ferry": "ferry",
    "feribot": "ferry",
}
MODE_WINDOW = 3
MIN_PARTIAL = 4
# Report vocabulary that some stops are also named. A bare mention of one is not a stop.
NOTICE_WORDS = frozenset(
    "stop station stops closed closure service services line lines trip trips delay delayed "
    "cancelled canceled running normal today tomorrow metro tram bus durak duragi istasyon "
    "kapali sefer hat hatti".split()
)


@dataclass(frozen=True)
class Place:
    key: tuple[str, ...]
    name: str
    stops: tuple[str, ...]


@dataclass(frozen=True)
class Mention:
    start: int
    end: int
    words: tuple[str, ...]
    stops: tuple[str, ...]
    exact: bool
    mode: str | None

    @property
    def ambiguous(self) -> bool:
        return len(self.stops) > 1


def feed_of(stop: str) -> str:
    return stop.partition(":")[0]


class Gazetteer:
    def __init__(self, places: list[Place]) -> None:
        self.exact: dict[tuple[str, ...], Place] = {place.key: place for place in places}
        self.partial: dict[tuple[str, ...], list[Place]] = defaultdict(list)
        for place in places:
            for size in range(1, min(len(place.key), MAX_WORDS + 1)):
                self.partial[place.key[:size]].append(place)

    @classmethod
    def build(cls, stops: Mapping[str, Stop]) -> "Gazetteer":
        grouped: dict[tuple[str, ...], list[str]] = defaultdict(list)
        names: dict[tuple[str, ...], str] = {}
        for stop in stops.values():
            key = tuple(WORD.findall(normalize(stop.name)))
            if not key or sum(len(word) for word in key) < 3 or set(key) <= NOTICE_WORDS:
                continue
            grouped[key].append(stop.id)
            names.setdefault(key, stop.name)
        return cls([Place(key, names[key], tuple(sorted(ids))) for key, ids in grouped.items()])

    def find(self, text: str) -> list[Mention]:
        value, offsets = folded(text)
        tokens = [(match.group(), match.start(), match.end()) for match in WORD.finditer(value)]
        mentions: list[Mention] = []
        index = 0
        while index < len(tokens):
            found = self._longest(tokens, index)
            if found is None:
                index += 1
                continue
            size, consumed, exact, stops, words = found
            exact_stops: set[str] = (
                set(self.exact[words].stops) if words in self.exact else set[str]()
            )
            first, last = tokens[index], tokens[index + consumed - 1]
            mode = self._mode(tokens, index, index + consumed)
            if mode is not None:
                narrowed = tuple(stop for stop in stops if feed_of(stop) == mode)
                stops = narrowed or stops
                exact = bool(stops) and set(stops) <= exact_stops
            end = offsets[last[2] - 1] + 1
            mentions.append(Mention(offsets[first[1]], end, words, stops, exact, mode))
            index += consumed
            del size
        return mentions

    def _longest(
        self, tokens: list[tuple[str, int, int]], index: int
    ) -> tuple[int, int, bool, tuple[str, ...], tuple[str, ...]] | None:
        for size in range(min(MAX_WORDS, len(tokens) - index), 0, -1):
            words = tuple(token[0] for token in tokens[index : index + size])
            options: list[tuple[tuple[str, ...], int]] = []
            attached, stemmed = self._suffixed(tokens, index, size)
            if attached is not None:
                options.append(attached)
            options.append((words, size))
            if stemmed is not None:
                options.append(stemmed)
            for candidate, used in options:
                exact = self.exact.get(candidate)
                partial = (
                    {s for p in self.partial.get(candidate, ()) for s in p.stops}
                    if sum(len(word) for word in candidate) >= MIN_PARTIAL
                    else set[str]()
                )
                if exact is not None or partial:
                    stops = tuple(sorted({*(exact.stops if exact else ()), *partial}))
                    return size, used, bool(exact) and not partial, stops, candidate
        return None

    @staticmethod
    def _suffixed(
        tokens: list[tuple[str, int, int]], index: int, size: int
    ) -> tuple[tuple[tuple[str, ...], int] | None, tuple[tuple[str, ...], int] | None]:
        """Read `Karataş'ta` (attached) or `Karataşta` (stemmed) as a name plus a case suffix."""
        words = tuple(token[0] for token in tokens[index : index + size])
        following = tokens[index + size] if index + size < len(tokens) else None
        attached = None
        if (
            following
            and following[0] in SUFFIXES
            and following[1] - tokens[index + size - 1][2] == 1
        ):
            attached = (words, size + 1)
        last = words[-1]
        stemmed = next(
            (
                ((*words[:-1], last[: -len(suffix)]), size)
                for suffix in sorted(SUFFIXES, key=len, reverse=True)
                if last.endswith(suffix) and len(last) - len(suffix) >= 3
            ),
            None,
        )
        return attached, stemmed

    @staticmethod
    def _mode(tokens: list[tuple[str, int, int]], start: int, end: int) -> str | None:
        window = tokens[max(0, start - MODE_WINDOW) : start] + tokens[end : end + MODE_WINDOW]
        modes = {MODE_WORDS[word] for word, _, _ in window if word in MODE_WORDS}
        return next(iter(modes)) if len(modes) == 1 else None
