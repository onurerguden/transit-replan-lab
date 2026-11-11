"""Create deterministic, stratified synthetic incidents against the pinned timetable."""

import hashlib
import json
from pathlib import Path
from random import Random

from trl.domain import (
    Constraint,
    Record,
    Scenario,
    StopClosure,
    TripCancellation,
    TripDelay,
)
from trl.gtfs import DATA_ROOT, Schedule, load_schedule
from trl.scenarios import load_scenario

FAMILIES = (
    "interchange",
    "platform",
    "cancellation",
    "delay",
    "ambiguous",
    "tight_window",
)


class Case(Record):
    family: str
    language: str
    ambiguous: bool
    ablation: bool
    scenario: Scenario


def stamp(seconds: int) -> str:
    return f"{seconds // 3600:02}:{seconds // 60 % 60:02}"


def make_case(schedule: Schedule, split: str, family: str, i: int, rng: Random) -> Case:
    base = load_scenario()
    start = (8 * 60 + 12 + rng.randrange(28)) * 60
    end = start + rng.choice((4500, 5100, 5700))
    a = Constraint(
        stop=rng.choice(("metro:1", "metro:3", "metro:4", "metro:9", "metro:14")),
        ready=start,
        wait_limit=rng.choice((360, 480, 600)),
        travel_limit=7200,
    )
    b = Constraint(
        stop=rng.choice(("tram:4", "tram:6", "tram:8", "tram:9")),
        ready=start + rng.choice((0, 120, 240)),
        wait_limit=rng.choice((360, 480, 600)),
    )
    stop_id = {
        "interchange": "tram:7",
        "tight_window": "tram:7",
        "ambiguous": "tram:7",
        "platform": ("tram:6", "tram:8", "tram:9", "tram:21")[i % 4],
    }.get(family, "tram:7")
    stop = schedule.stops[stop_id].name
    tr = i % 2 == 0
    incident: StopClosure | TripDelay | TripCancellation = StopClosure(
        stop=stop_id,
        start=start,
        end=end,
    )
    if family in {"delay", "cancellation"}:
        trips = [
            trip
            for trip in schedule.trips.values()
            if schedule.runs(trip.service, base.service_date)
            and start <= trip.calls[0].departure < start + 2400
        ]
        trip_id = rng.choice(trips).id
        if family == "delay":
            minutes = rng.choice((5, 8, 12, 15))
            incident = TripDelay(
                trip=trip_id, service_date=base.service_date, seconds=minutes * 60
            )
            if split == "dev":
                text = (
                    f"{trip_id} seferi {minutes} dakika gecikiyor."
                    if tr
                    else (f"Trip {trip_id} is delayed by {minutes} minutes.")
                )
            else:
                text = (
                    f"Gecikme bildirimi: {trip_id} seferi, {minutes} dakika."
                    if tr
                    else (f"Running {minutes} minutes behind schedule: trip {trip_id}.")
                )
        else:
            incident = TripCancellation(trip=trip_id, service_date=base.service_date)
            if split == "dev":
                text = (
                    f"{trip_id} seferi iptal edildi."
                    if tr
                    else f"Trip {trip_id} is cancelled."
                )
            else:
                text = (
                    f"İptal kaydı: {trip_id} seferi bugün çalışmayacak."
                    if tr
                    else (
                        f"Service update: cancel trip {trip_id} for this timetable day."
                    )
                )
    elif family == "ambiguous":
        text = (
            f"Konak {stamp(start)} ile {stamp(end)} arası kapalı."
            if tr
            else (f"Konak is closed from {stamp(start)} to {stamp(end)}.")
        )
    elif split == "dev":
        text = (
            f"{stop} tramvay durağı {stamp(start)} ile {stamp(end)} arasında kapalı."
            if tr
            else (
                f"The {stop} tram stop is closed from {stamp(start)} to {stamp(end)}."
            )
        )
    else:
        text = (
            f"{stamp(start)}–{stamp(end)} arasında {stop} tramvay durağına giriş ve çıkış kapalı."
            if tr
            else (
                f"Temporary closure of the {stop} tram platform, {stamp(start)}–{stamp(end)}."
            )
        )
    scenario = Scenario(
        id=f"{split}-{family}-{i:02d}",
        service_date=base.service_date,
        a=a,
        b=b,
        destinations=("tram:3", "tram:5") if i % 4 == 3 else ("tram:3",),
        meeting_start=start + 240,
        meeting_end=start + 360 if family == "tight_window" else end,
        incident=incident,
        notice=text,
    )
    return Case(
        family=family,
        language="tr" if tr else "en",
        ambiguous=family == "ambiguous",
        ablation=split == "locked" and family in {"interchange", "platform"} and i < 6,
        scenario=scenario,
    )


def build(root: Path) -> None:
    schedule = load_schedule()
    manifest: dict[str, str] = {}
    for split, seed, count in (("dev", 142, 4), ("locked", 573, 10)):
        rng = Random(seed)
        cases = [
            make_case(schedule, split, family, i, rng)
            for family in FAMILIES
            for i in range(count)
        ]
        data = "".join(case.model_dump_json() + "\n" for case in cases).encode()
        directory = root / split
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "cases.jsonl").write_bytes(data)
        manifest[split] = hashlib.sha256(data).hexdigest()
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    build(DATA_ROOT / "scenarios")
