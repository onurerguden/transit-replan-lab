"""Build a synthetic phrase-grounding corpus separate from the routing benchmark."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from random import Random

from trl.agents import PROMPT_DIR
from trl.gtfs import load_schedule
from trl.intake import extract, parse_incident
from trl.scenarios import load_scenario
from trl.vnext import Extraction, ExtractionQuote, Slot

ROOT = Path(".local/vnext-training-v2")


def overlap(train: Path, valid: Path) -> set[str]:
    def notices(path: Path) -> set[str]:
        return {
            json.loads(line)["messages"][1]["content"]
            for line in path.read_text().splitlines()
        }

    return notices(train) & notices(valid)


def audit_splits(root: Path) -> dict[str, object]:
    schedule, day = load_schedule(), load_scenario().service_date
    signatures: list[set[str]] = []
    distributions: dict[str, dict[str, int]] = {}
    for split in ("train", "valid"):
        events: set[str] = set()
        counts: Counter[str] = Counter()
        for number, line in enumerate(
            (root / f"{split}.jsonl").read_text().splitlines()
        ):
            messages = json.loads(line)["messages"]
            notice = json.loads(messages[1]["content"])["notice"]
            proposal = Extraction.model_validate_json(messages[2]["content"])
            if any(quote.quote not in notice for quote in proposal.quotes):
                raise ValueError(
                    f"{split} row {number + 1} contains an ungrounded quote."
                )
            facts, reasons = extract(notice, schedule, day, proposal)
            values = {fact.slot: fact.value for fact in facts}
            event = (
                None
                if reasons or not {"kind", "target"} <= values.keys()
                else parse_incident(values, schedule, day)
            )
            if event is None:
                raise ValueError(f"{split} row {number + 1} has no grounded event.")
            events.add(event.model_dump_json())
            # The generator emits a Turkish row followed by its English counterpart.
            counts[f"{event.kind}/{'en' if number % 2 else 'tr'}"] += 1
        signatures.append(events)
        distributions[split] = dict(sorted(counts.items()))
    return {
        "exact_overlap": len(overlap(root / "train.jsonl", root / "valid.jsonl")),
        "event_overlap": len(signatures[0] & signatures[1]),
        "family_language_counts": distributions,
    }


def build(root: Path = ROOT) -> None:
    root.mkdir(parents=True, exist_ok=True)
    schedule = load_schedule()
    day = load_scenario().service_date
    trips = tuple(
        trip.id for trip in schedule.trips.values() if schedule.runs(trip.service, day)
    )
    stops = tuple(
        stop.name for stop in schedule.stops.values() if stop.id.startswith("tram:")
    )
    prompt = (PROMPT_DIR / "operator_vnext.md").read_text()
    rng = Random(428)
    for split_number, (split, size, hour) in enumerate(
        (("train", 360, 16), ("valid", 60, 18))
    ):
        # Trip events have no clock slot: separate their identities across splits.
        split_trips = trips[split_number::2]
        with (root / f"{split}.jsonl").open("w", encoding="utf-8") as handle:
            for index in range(size):
                tr = index % 2 == 0
                fields: list[tuple[Slot, str]]
                family = index // 2 % 3
                if family == 0:
                    target = rng.choice(stops)
                    action = "giriş çıkış yok" if tr else "out of service"
                    start = f"{hour:02d}:{index % 60:02d}"
                    end = f"{hour + 1:02d}:{(index * 7 + index // 60) % 60:02d}"
                    notice = (
                        f"{target} tramvay durağında {start} ile {end} arasında {action}."
                        if tr
                        else f"{target} tram stop is {action} from {start} to {end}."
                    )
                    fields = [
                        ("kind", action),
                        ("target", target),
                        ("start", start),
                        ("end", end),
                    ]
                elif family == 1:
                    target = split_trips[index // 2]
                    action = "geç geliyor" if tr else "running behind"
                    duration = f"{index // 2 % 45 + 1} " + (
                        "dakika" if tr else "minutes"
                    )
                    notice = (
                        f"{target} seferi {duration} {action}."
                        if tr
                        else f"Trip {target} is {action} by {duration}."
                    )
                    fields = [("kind", action), ("target", target), ("delay", duration)]
                else:
                    target = split_trips[index // 2]
                    action = "seferden çekildi" if tr else "taken off the timetable"
                    notice = (
                        f"{target} {action}." if tr else f"Trip {target} was {action}."
                    )
                    fields = [("kind", action), ("target", target)]
                output = Extraction(
                    quotes=tuple(
                        ExtractionQuote(slot=slot, quote=quote)
                        for slot, quote in fields
                    )
                )
                row = {
                    "messages": [
                        {"role": "system", "content": prompt},
                        {
                            "role": "user",
                            "content": json.dumps(
                                {"notice": notice}, ensure_ascii=False
                            ),
                        },
                        {"role": "assistant", "content": output.model_dump_json()},
                    ]
                }
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    audit = audit_splits(root)
    if audit["exact_overlap"] or audit["event_overlap"]:
        raise ValueError(f"Training/validation overlap: {audit}")
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "version": 2,
                "training_status": "not_trained",
                "split_policy": "Disjoint closure windows and trip IDs; shared language templates are intentional, not a linguistic holdout.",
                **audit,
                "sha256": {
                    split: hashlib.sha256(
                        (root / f"{split}.jsonl").read_bytes()
                    ).hexdigest()
                    for split in ("train", "valid")
                },
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT)
    build(parser.parse_args().output)
