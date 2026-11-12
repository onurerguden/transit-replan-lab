"""Build a synthetic phrase-grounding corpus separate from the routing benchmark."""

import json
from pathlib import Path
from random import Random

from trl.agents import PROMPT_DIR
from trl.gtfs import load_schedule
from trl.scenarios import load_scenario
from trl.vnext import Extraction, ExtractionQuote, Slot

ROOT = Path(".local/vnext-training")


def build() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
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
    for split, size, hour in (("train", 360, 16), ("valid", 60, 17)):
        with (ROOT / f"{split}.jsonl").open("w", encoding="utf-8") as handle:
            for index in range(size):
                tr = index % 2 == 0
                fields: list[tuple[Slot, str]]
                if index % 6 in {0, 1, 2, 3}:
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
                elif index % 6 == 4:
                    target = trips[index]
                    action = "geç geliyor"
                    duration = f"{index % 45 + 1} dakika"
                    notice = f"{target} seferi {duration} {action}."
                    fields = [("kind", action), ("target", target), ("delay", duration)]
                else:
                    target = trips[index]
                    action = "taken off the timetable"
                    notice = f"Trip {target} was {action}."
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


if __name__ == "__main__":
    build()
