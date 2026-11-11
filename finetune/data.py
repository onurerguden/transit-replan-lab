"""Generate disjoint template families for supervised operator adaptation."""

import argparse
import hashlib
import json
from pathlib import Path
from random import Random

from trl.agents import NoticeDecision
from trl.domain import Record
from trl.gtfs import Schedule, load_schedule
from trl.scenarios import load_scenario

MODEL_REVISION = "0e7ffd5c629ef7719d4cbc04069232580bfa9d9c"
FAMILIES = (
    "closure",
    "cancellation",
    "delay",
    "ambiguous",
    "missing_time",
    "unknown_stop",
)
SYSTEM = (
    "Extract one transit incident from the notice. Return exactly one JSON object. "
    "Use kind stop_closure with stop, start and end (HH:MM); trip_cancellation with trip; "
    "trip_delay with trip and integer minutes; or clarify. Copy identifiers from the supplied "
    "catalogue. Ask to clarify an ambiguous target, a missing interval, or an unknown identifier."
)


class Message(Record):
    role: str
    content: str


class Example(Record):
    id: str
    family: str
    language: str
    template: str
    messages: tuple[Message, ...]


def format_notice(
    split: str,
    family: str,
    tr: bool,
    stop: str,
    trip: str,
    start: str,
    end: str,
    delay: int,
    number: int,
) -> str:
    t = (
        f"{stop} durağı {start} ile {end} arasında kapalı.",
        f"{trip} seferi iptal edildi.",
        f"{trip} seferi {delay} dakika gecikiyor.",
        f"Konak {start} ile {end} arasında kapalı.",
        f"{stop} durağı geçici olarak kapatıldı.",
        f"Kaydı bulunmayan Sahil-{number} durağı {start}–{end} arası kapalı.",
    )
    e = (
        f"The {stop} stop is closed from {start} to {end}.",
        f"Trip {trip} is cancelled.",
        f"Trip {trip} is delayed by {delay} minutes.",
        f"Konak is closed from {start} to {end}.",
        f"The {stop} stop is temporarily closed.",
        f"Harbour-{number} stop is shut from {start} to {end}.",
    )
    if split == "valid":
        t = (
            f"{start}–{end} hizmet kesintisi: {stop} durağına giriş çıkış kapalı.",
            f"Bugünkü çizelgede {trip} seferini çalıştırmayın.",
            f"Gecikme kaydı: {trip}, +{delay} dakika.",
            f"Kesinti noktası Konak; zaman aralığı {start}–{end}.",
            f"Kapanış noktası {stop}. Saatler henüz duyurulmadı.",
            f"Bildirim: Sahil-{number} durağına {start} ve {end} arasında erişim yok.",
        )
        e = (
            f"Access suspended at {stop} between {start} and {end}.",
            f"Service update: remove scheduled trip {trip} today.",
            f"Running {delay} minutes behind schedule: trip {trip}.",
            f"Closure location: Konak, {start}–{end}.",
            f"Dispatch closed {stop}; the operating interval is unconfirmed.",
            f"Access suspended at Harbour-{number}, {start}–{end}.",
        )
    elif split == "test":
        t = (
            f"İşletim notu: {start} sonrasında {stop} kullanılamaz; açılış {end}.",
            f"Hareket planı güncellendi, {trip} seferi tamamen kaldırıldı.",
            f"{trip} yolculuğunun kalkışı tarifeye göre {delay} dakika ileri alındı.",
            f"{start} başlangıç, {end} bitiş: Konak yolcu erişimine kapalı.",
            f"{stop} için kapanış var fakat başlangıç ve bitiş verilmedi.",
            f"Sahil-{number} için yolcu erişimi {start} itibarıyla yok, {end} dönüş.",
        )
        e = (
            f"Dispatch bulletin: block {stop} starting at {start}; reopen at {end}.",
            f"Trip {trip} has been dropped from the operating timetable.",
            f"Move the departure of {trip} back by {delay} minutes.",
            f"Passenger access suspended at Konak, starting {start}, reopening {end}.",
            f"{stop} has been shut. Start and reopening times have yet to be set.",
            f"Dispatch has blocked Harbour-{number} from {start}; reopen at {end}.",
        )
    return (t if tr else e)[FAMILIES.index(family)]


def generate(schedule: Schedule, split: str, amount: int, seed: int) -> list[Example]:
    rng = Random(seed)
    day = load_scenario().service_date
    trips = sorted(
        trip.id for trip in schedule.trips.values() if schedule.runs(trip.service, day)
    )
    stops = sorted(schedule.stops)
    assigned = rng.sample(trips, 2 * amount)
    rows: list[Example] = []
    for family in FAMILIES:
        for n in range(amount):
            tr = n % 2 == 0
            language = "tr" if tr else "en"
            stop = rng.choice(stops)
            trip = assigned[n if family == "cancellation" else amount + n]
            minute = (seed + n * 7) % 600 + 420
            start = f"{minute // 60:02}:{minute % 60:02}"
            end_minute = minute + rng.choice((12, 18, 30, 42))
            end = f"{end_minute // 60:02}:{end_minute % 60:02}"
            delay = rng.randrange(3, 26)
            catalog = sorted({stop, "metro:2", "tram:7", *rng.sample(stops, 3)})
            notice = format_notice(
                split,
                family,
                tr,
                schedule.stops[stop].name,
                trip,
                start,
                end,
                delay,
                seed + n,
            )
            expected = NoticeDecision(kind="clarify")
            if family == "closure":
                expected = NoticeDecision(
                    kind="stop_closure", stop=stop, start=start, end=end
                )
                # Duplicate display names are disambiguated in the notice itself.
                if (
                    sum(
                        item.name == schedule.stops[stop].name
                        for item in schedule.stops.values()
                    )
                    > 1
                ):
                    notice += f" [{stop}]"
            elif family == "cancellation":
                expected = NoticeDecision(kind="trip_cancellation", trip=trip)
            elif family == "delay":
                expected = NoticeDecision(kind="trip_delay", trip=trip, minutes=delay)
            details = {
                "notice": notice,
                "stops": [[key, schedule.stops[key].name] for key in catalog],
                "trips": sorted({trip, *rng.sample(trips, 2)}),
            }
            rows.append(
                Example(
                    id=f"{split}-{family}-{n:02d}",
                    family=family,
                    language=language,
                    template=f"{split}:{family}:{language}",
                    messages=(
                        Message(role="system", content=SYSTEM),
                        Message(
                            role="user", content=json.dumps(details, ensure_ascii=False)
                        ),
                        Message(
                            role="assistant",
                            content=expected.model_dump_json(exclude_none=True),
                        ),
                    ),
                )
            )
    rng.shuffle(rows)
    return rows


def build(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    schedule = load_schedule()
    manifest: dict[str, dict[str, object]] = {}
    template_ids: set[str] = set()
    notices: set[str] = set()
    for split, amount, seed in (
        ("train", 60, 301),
        ("valid", 10, 711),
        ("test", 10, 1117),
    ):
        batch = generate(schedule, split, amount, seed)
        templates = {example.template for example in batch}
        contents = {
            json.loads(example.messages[1].content)["notice"] for example in batch
        }
        if template_ids & templates or notices & contents:
            raise ValueError("Examples or template families overlap across partitions.")
        template_ids.update(templates)
        notices.update(contents)
        raw = "".join(example.model_dump_json() + "\n" for example in batch).encode()
        (output / f"{split}.jsonl").write_bytes(raw)
        manifest[split] = {
            "count": len(batch),
            "unique_notices": len(contents),
            "templates": sorted(templates),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".local/finetune/data"))
    args = parser.parse_args()
    build(args.output)


if __name__ == "__main__":
    main()
