# pyright: basic
"""Prove the splits are disjoint before any model reads the test split."""

import hashlib
import json
import re
from pathlib import Path

from trl.intake import INDIRECT
from trl.notice import ACTIONS, normalize

from experiments.bench_v3 import generate
from experiments.bench_v3.generate import SIZES, SPLITS, Report

MASK = re.compile(r"\d+|[A-Za-zÇĞİÖŞÜçğıöşü]+:[\w\-]+")


def mask(text: str, names: list[str]) -> str:
    value = normalize(text)
    for name in sorted(names, key=len, reverse=True):
        value = value.replace(normalize(name), "<stop>")
    return MASK.sub("<n>", value)


def audit(data: dict[str, list[Report]], stops: dict[str, str]) -> list[str]:
    problems: list[str] = []
    owners = generate.assign_stops(stops)
    names = list(stops.values())
    part_owner: dict[str, str] = {}
    texts: dict[str, str] = {}
    templates: dict[str, str] = {}
    for split in SPLITS:
        rows = data[split]
        if len(rows) != 2 * SIZES[split]:
            problems.append(
                f"{split}: expected {2 * SIZES[split]} reports, found {len(rows)}."
            )
        if len({row.group for row in rows}) != SIZES[split]:
            problems.append(f"{split}: group count mismatch.")
        for row in rows:
            for part in row.parts:
                if part_owner.setdefault(part, split) != split:
                    problems.append(
                        f"Part {part} appears in {part_owner[part]} and {split}."
                    )
            if any(
                owners.get(stop, split) != split for stop in row.stops if stop in owners
            ):
                problems.append(f"{row.id}: stop belongs to another split.")
            digest = hashlib.sha256(row.text.encode()).hexdigest()
            if texts.setdefault(digest, split) != split:
                problems.append(
                    f"{row.id}: exact text also appears in {texts[digest]}."
                )
            shape = mask(row.text, names)
            if templates.setdefault(shape, split) != split:
                problems.append(
                    f"{row.id}: masked template also appears in {templates[shape]}."
                )
    for part, split in generate_parts().items():
        if part_owner.get(part, split) != split:
            problems.append(f"Declared split of {part} disagrees with its use.")
    for row in data["test"]:
        if row.kind_phrase and row.family in generate.APPLY | generate.ASK:
            value = normalize(row.kind_phrase)
            hit = row.family not in {"delay", "cancellation"} and (
                ACTIONS["stop_closure"].search(value)
                or any(pattern.search(value) for pattern in INDIRECT.values())
            )
            if hit:
                problems.append(
                    f"{row.id}: test phrase {row.kind_phrase!r} is in the lexicon."
                )
    return list(dict.fromkeys(problems))


def generate_parts() -> dict[str, str]:
    banks = (
        generate.CLOSED,
        generate.LEADS,
        generate.TIME_FORMS,
        generate.NOTES,
        generate.CALM,
    )
    return {
        item[0]: item[1] for bank in banks for items in bank.values() for item in items
    }


def manifest(paths: dict[str, Path], seed: int, code: list[Path]) -> dict[str, object]:
    return {
        "seed": seed,
        "sizes": SIZES,
        "files": {
            split: hashlib.sha256(path.read_bytes()).hexdigest()
            for split, path in paths.items()
        },
        "generator": hashlib.sha256(
            b"".join(item.read_bytes() for item in code)
        ).hexdigest(),
    }


def write_manifest(path: Path, content: dict[str, object]) -> None:
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n")
