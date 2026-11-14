"""Retrieve the train-bank reports that read most like a new report, as few-shot examples.

The Operator's only contribution is the quote that names the event. Retrieval therefore looks
for reports whose wording is close after the stop names, numbers and identifiers are masked,
and returns each with the reply a perfect Operator would give. The index holds train reports
only. A query never returns a report with its own masked template, so a training row cannot
retrieve itself or its template siblings.

Scoring is TF-IDF over character four-grams with an inverted index. It needs no model, is
deterministic, and breaks ties by index order.
"""

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from experiments.bench_v3 import catalogue
from experiments.bench_v3.audit import mask
from experiments.bench_v3.generate import Report, read
from finetune.v2_data import target

GRAM = 4


@dataclass(frozen=True)
class Exemplar:
    notice: str
    reply: str
    template: str


def grams(text: str) -> Counter[str]:
    padded = f" {text} "
    return Counter(padded[i : i + GRAM] for i in range(max(1, len(padded) - GRAM + 1)))


class Index:
    def __init__(self, reports: list[Report], names: list[str]) -> None:
        self.names = names
        self.items: list[Exemplar] = []
        seen: set[str] = set()
        for report in reports:
            template = mask(report.text, names)
            reply = target(report)
            if template in seen or reply is None:
                continue
            seen.add(template)
            self.items.append(
                Exemplar(
                    report.text, reply.model_dump_json(exclude_none=True), template
                )
            )
        counts = [grams(item.template) for item in self.items]
        document_frequency: Counter[str] = Counter(g for c in counts for g in c)
        total = len(self.items)
        self.idf = {
            g: math.log((1 + total) / (1 + n)) + 1
            for g, n in document_frequency.items()
        }
        self.postings: dict[str, list[tuple[int, float]]] = {}
        for number, count in enumerate(counts):
            vector = self.weigh(count)
            for gram, weight in vector.items():
                self.postings.setdefault(gram, []).append((number, weight))

    def weigh(self, count: Counter[str]) -> dict[str, float]:
        raw = {
            g: (1 + math.log(n)) * self.idf[g]
            for g, n in count.items()
            if g in self.idf
        }
        norm = math.sqrt(sum(v * v for v in raw.values())) or 1.0
        return {g: v / norm for g, v in raw.items()}

    def retrieve(self, text: str, k: int = 4) -> list[Exemplar]:
        template = mask(text, self.names)
        query = self.weigh(grams(template))
        scores: Counter[int] = Counter()
        for gram, weight in query.items():
            for number, other in self.postings.get(gram, ()):
                scores[number] += weight * other
        ranked = sorted(scores, key=lambda number: (-scores[number], number))
        picked: list[Exemplar] = []
        replies: set[str] = set()
        for number in ranked:
            item = self.items[number]
            if item.template == template or (
                item.reply in replies and len(picked) < k - 1
            ):
                continue
            picked.append(item)
            replies.add(item.reply)
            if len(picked) == k:
                break
        return picked


def build(path: Path = Path("data/bench/v3/train.jsonl")) -> Index:
    stops, _, _ = catalogue.load()
    return Index(read(path), list(stops.values()))


def view(index: Index, text: str, k: int = 4) -> str:
    """The user message of a retrieval-augmented request."""
    return json.dumps(
        {
            "notice": text,
            "examples": [
                {"notice": e.notice, "reply": json.loads(e.reply)}
                for e in index.retrieve(text, k)
            ],
        },
        ensure_ascii=False,
    )
