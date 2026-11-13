# pyright: basic
"""Build the TRL-Bench v3 reports from phrase parts that belong to exactly one split.

Every sentence combines a predicate, a time form and a lead-in. Each part carries an ID and a
split, so a sentence is traceable to the parts that made it and the audit can prove that no part
is shared across splits. Stops are partitioned the same way: a fifth of the stops only appear in
test. The test predicates deliberately avoid the production lexicon, so a deterministic reader
cannot score on them and a model has to supply the event kind.
"""

import hashlib
import json
import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from experiments.bench_v3 import morph_tr

Split = Literal["train", "dev", "calibration", "test"]
Lang = Literal["en", "tr"]
Action = Literal["apply", "ask", "abstain"]
SPLITS: tuple[Split, ...] = ("train", "dev", "calibration", "test")
SIZES: dict[Split, int] = {"train": 3000, "dev": 600, "calibration": 300, "test": 1000}
FAMILIES = (
    "closure_range", "closure_until", "closure_from", "closure_note", "closure_pair",
    "delay", "cancellation", "ambiguous_stop", "negated", "hedged", "wrong_date",
    "foreign_zone", "unrelated",
)  # fmt: skip
APPLY = {"closure_range", "closure_note", "closure_pair", "delay", "cancellation"}
ASK = {"closure_until", "closure_from", "ambiguous_stop"}

# Parts: (id, split, text). Predicates name the event; `kind` is its gold label.
CLOSED = {
    "en": [
        ("en-cl-1", "train", "is closed"), ("en-cl-2", "train", "has been closed"),
        ("en-cl-3", "dev", "remains closed"), ("en-cl-4", "dev", "is closed to passengers"),
        ("en-cl-5", "calibration", "will be closed"), ("en-cl-6", "calibration", "is closed off"),
        ("en-cl-7", "test", "is suspended"), ("en-cl-8", "test", "is shuttered"),
        ("en-cl-9", "test", "is unavailable to riders"), ("en-cl-10", "test", "is off limits to passengers"),
    ],
    "tr": [
        ("tr-cl-1", "train", "kapalıdır"), ("tr-cl-2", "train", "kapatılmıştır"),
        ("tr-cl-3", "dev", "kapalı olacaktır"), ("tr-cl-4", "dev", "kapalı kalacaktır"),
        ("tr-cl-5", "calibration", "kapatıldı"), ("tr-cl-6", "calibration", "kapalı durumdadır"),
        ("tr-cl-7", "test", "hizmet dışıdır"), ("tr-cl-8", "test", "yolcu alımına durdurulmuştur"),
        ("tr-cl-9", "test", "hizmet sunamamaktadır"), ("tr-cl-10", "test", "hizmet vermeyecektir"),
    ],
}  # fmt: skip
LEADS = {
    "en": [
        ("en-ld-1", "train", ""), ("en-ld-2", "train", "Notice: "), ("en-ld-3", "dev", "Update: "),
        ("en-ld-4", "dev", "Attention riders. "), ("en-ld-5", "calibration", "Service alert: "),
        ("en-ld-6", "test", "Passengers are informed that "), ("en-ld-7", "test", "FYI: "),
        ("en-ld-8", "test", "Operations report: "),
    ],
    "tr": [
        ("tr-ld-1", "train", ""), ("tr-ld-2", "train", "Duyuru: "), ("tr-ld-3", "dev", "Bilgi: "),
        ("tr-ld-4", "dev", "Sayın yolcularımız, "), ("tr-ld-5", "calibration", "Uyarı: "),
        ("tr-ld-6", "test", "Yolcularımıza duyurulur: "), ("tr-ld-7", "test", "Not: "),
        ("tr-ld-8", "test", "Operasyon bildirimi: "),
    ],
}  # fmt: skip
TIME_FORMS = {
    "en": [
        ("en-tm-1", "train", "from {a} to {b}"), ("en-tm-2", "train", "between {a} and {b}"),
        ("en-tm-3", "dev", "{a}-{b}"), ("en-tm-4", "dev", "starting {a} until {b}"),
        ("en-tm-5", "calibration", "from {a} until {b}"),
        ("en-tm-6", "test", "until {b}, from {a}"), ("en-tm-7", "test", "from {a} through {b}"),
        ("en-tm-8", "test", "for the period {a} to {b}"),
    ],
    "tr": [
        ("tr-tm-1", "train", "{a} ile {b} arasında"), ("tr-tm-2", "train", "{a}-{b} arası"),
        ("tr-tm-3", "dev", "saat {a} ile {b} arasında"), ("tr-tm-4", "dev", "{a} ile {b} saatleri arasında"),
        ("tr-tm-5", "calibration", "{a} ve {b} arasında"),
        ("tr-tm-6", "test", "{a_abl} {b_dat} kadar"), ("tr-tm-7", "test", "{b_dat} kadar, {a_abl} itibaren"),
        ("tr-tm-8", "test", "{a_abl} {b_dat} dek"),
    ],
}  # fmt: skip
CALM = {
    "en": [
        ("en-cm-1", "train", "Services are running normally today."),
        ("en-cm-2", "dev", "All lines are operating as scheduled."),
        ("en-cm-3", "calibration", "No changes to today's timetable."),
        ("en-cm-4", "test", "Trains and trams are on time this morning."),
    ],
    "tr": [
        ("tr-cm-1", "train", "Seferler bugün normal seyrinde devam etmektedir."),
        ("tr-cm-2", "dev", "Tüm hatlarda seferler tarifesine uygundur."),
        ("tr-cm-3", "calibration", "Bugünkü tarifede bir değişiklik yoktur."),
        ("tr-cm-4", "test", "Metro ve tramvay bu sabah zamanında çalışmaktadır."),
    ],
}  # fmt: skip
NOTES = {
    "en": [("en-nt-1", "train", "(no lifts)"), ("en-nt-2", "dev", "No parking is available."),
           ("en-nt-3", "calibration", "(no ramp)"), ("en-nt-4", "test", "Do not use the lift.")],
    "tr": [("tr-nt-1", "train", "(asansör yok)"), ("tr-nt-2", "dev", "Otopark mevcut değildir."),
           ("tr-nt-3", "calibration", "(rampa yok)"), ("tr-nt-4", "test", "Asansörü kullanmayınız.")],
}  # fmt: skip


@dataclass(frozen=True)
class Part:
    id: str
    split: str
    text: str


@dataclass(frozen=True)
class Report:
    id: str
    group: str
    split: Split
    lang: Lang
    family: str
    text: str
    action: Action
    incidents: tuple[dict[str, object], ...]
    slot: str | None
    answer: str | None
    parts: tuple[str, ...]
    stops: tuple[str, ...]
    kind_phrase: str | None


def pick(bank: list[tuple[str, str, str]], split: Split, rng: random.Random) -> Part:
    return Part(*rng.choice([item for item in bank if item[1] == split]))


def assign_stops(stops: dict[str, str]) -> dict[str, Split]:
    """Give every stop to exactly one split by hash rank: 20% test, 10% dev, 10% calibration."""
    ranked = sorted(stops, key=lambda stop: hashlib.sha256(stop.encode()).hexdigest())
    total = len(ranked)
    cuts = (round(total * 0.2), round(total * 0.3), round(total * 0.4))
    return {
        stop: "test"
        if rank < cuts[0]
        else "dev"
        if rank < cuts[1]
        else "calibration"
        if rank < cuts[2]
        else "train"
        for rank, stop in enumerate(ranked)
    }


def clock(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}"


def build_report(
    index: int,
    split: Split,
    family: str,
    stops: dict[str, str],
    trips: list[str],
    rng: random.Random,
    owners: dict[str, Split],
) -> list[Report]:
    allowed = [stop for stop in stops if owners[stop] == split]  # one split per stop
    start = rng.randrange(6 * 3600, 20 * 3600, 60)
    end = start + rng.randrange(20, 240, 5) * 60
    stop = rng.choice(allowed)
    other = rng.choice([item for item in allowed if item != stop])
    trip = rng.choice(trips)
    minutes = rng.randrange(3, 55)
    group = f"{split}-{index:05d}"
    reports: list[Report] = []
    for lang in ("en", "tr"):
        reports.append(
            realize(
                group,
                lang,
                split,
                family,
                stops,
                stop,
                other,
                trip,
                start,
                end,
                minutes,
                rng,
            )  # pyright: ignore[reportArgumentType]
        )
    return reports


def realize(
    group: str,
    lang: Lang,
    split: Split,
    family: str,
    stops: dict[str, str],
    stop: str,
    other: str,
    trip: str,
    start: int,
    end: int,
    minutes: int,
    rng: random.Random,
) -> Report:
    predicate = pick(CLOSED[lang], split, rng)
    lead = pick(LEADS[lang], split, rng)
    form = pick(TIME_FORMS[lang], split, rng)
    note = pick(NOTES[lang], split, rng)
    name, other_name = stops[stop], stops[other]
    a, b = clock(start), clock(end)
    times = form.text.format(
        a=a, b=b,
        a_abl=morph_tr.clock_ablative(a) if lang == "tr" else a,
        b_dat=morph_tr.clock_dative(b) if lang == "tr" else b,
    )  # fmt: skip
    mode = stop.partition(":")[0]
    subject = (
        f"{name} {'tram stop' if mode == 'tram' else 'metro station'}"
        if lang == "en"
        else f"{name} {'tramvay durağı' if mode == 'tram' else 'metro istasyonu'}"
    )
    parts = [predicate.id, lead.id, form.id]
    action: Action = "apply"
    incidents: list[dict[str, object]] = []
    slot: str | None = None
    answer: str | None = None
    stops_used = (stop,)
    kind_phrase: str | None = predicate.text
    closure = {"kind": "stop_closure", "stop": stop, "start": start, "end": end}
    if family == "closure_range":
        text = f"{lead.text}{subject} {predicate.text} {times}."
        incidents = [closure]
    elif family == "closure_note":
        text = f"{lead.text}{subject} {predicate.text} {times}. {note.text}"
        incidents, parts = [closure], [*parts, note.id]
    elif family == "closure_pair":
        joiner = "and" if lang == "en" else "ve"
        pair = f"{name} {joiner} {other_name}"
        plural = "tram stops" if lang == "en" else "tramvay durakları"
        if other.partition(":")[0] != "tram" or stop.partition(":")[0] != "tram":
            plural = "stops" if lang == "en" else "durakları"
        verb = (
            predicate.text.replace("is ", "are ")
            .replace("has been", "have been")
            .replace("remains", "remain")
            if lang == "en"
            else predicate.text
        )
        text = f"{lead.text}{pair} {plural} {verb} {times}."
        incidents = [closure, {**closure, "stop": other}]
        stops_used = (stop, other)
    elif family in {"closure_until", "closure_from"}:
        action, slot = "ask", "start" if family == "closure_until" else "end"
        if lang == "en":
            text = f"{lead.text}{subject} {predicate.text} " + (
                f"until {b}." if slot == "start" else f"from {a}."
            )
        else:
            text = f"{lead.text}{subject} " + (
                f"{morph_tr.clock_dative(b)} kadar {predicate.text}."
                if slot == "start"
                else f"{morph_tr.clock_ablative(a)} itibaren {predicate.text}."
            )
        answer = a if slot == "start" else b
        incidents = [closure]
    elif family == "ambiguous_stop":
        action, slot = "ask", "target"
        text = f"{lead.text}Konak {predicate.text} {times}."
        answer = "Konak İskele tram" if lang == "en" else "Konak İskele tramvay"
        incidents = [
            {"kind": "stop_closure", "stop": "tram:7", "start": start, "end": end}
        ]
        stops_used = ("tram:7",)
    elif family == "delay":
        word = "late" if lang == "en" else "gecikmeli"
        text = (
            f"{lead.text}Trip {trip} is {minutes} minutes {word}."
            if lang == "en"
            else f"{lead.text}{trip} seferi {minutes} dakika {word}."
        )
        incidents = [{"kind": "trip_delay", "trip": trip, "seconds": minutes * 60}]
        stops_used, kind_phrase = (), word
    elif family == "cancellation":
        text = (
            f"{lead.text}Trip {trip} is cancelled."
            if lang == "en"
            else f"{lead.text}{trip} seferi iptal edilmiştir."
        )
        incidents = [{"kind": "trip_cancellation", "trip": trip}]
        stops_used, kind_phrase = (), "cancelled" if lang == "en" else "iptal"
    elif family == "negated":
        action, incidents = "abstain", []
        text = (
            f"{lead.text}{subject} is not closed {times}."
            if lang == "en"
            else f"{lead.text}{subject} {times} kapalı değildir."
        )
    elif family == "hedged":
        action, incidents = "abstain", []
        text = (
            f"{lead.text}{subject} might be closed {times}."
            if lang == "en"
            else f"{lead.text}{subject} {times} kapalı olabilir."
        )
    elif family == "wrong_date":
        action, incidents = "abstain", []
        other_day = date(2026, 11, 3 + rng.randrange(20))
        label = (
            other_day.isoformat() if lang == "en" else other_day.strftime("%d.%m.%Y")
        )
        text = (
            f"{lead.text}On {label}, {subject} {predicate.text} {times}."
            if lang == "en"
            else f"{lead.text}{label} tarihinde {subject} {predicate.text} {times}."
        )
    elif family == "foreign_zone":
        action, incidents = "abstain", []
        text = (
            f"{lead.text}{subject} {predicate.text} from {a} UTC to {b} UTC."
            if lang == "en"
            else f"{lead.text}{subject} {a} UTC ile {b} UTC arasında {predicate.text}."
        )
    else:
        action, incidents, kind_phrase = "abstain", [], None
        calm = pick(CALM[lang], split, rng)
        parts.append(calm.id)
        text = f"{lead.text}{calm.text}"
    identifier = f"{group}-{lang}"
    return Report(
        identifier, group, split, lang, family, text, action, tuple(incidents), slot, answer,
        tuple(parts), stops_used, kind_phrase if family in APPLY | ASK else None,
    )  # fmt: skip


def build(
    split: Split, stops: dict[str, str], trips: list[str], seed: int
) -> list[Report]:
    rng = random.Random(f"{seed}:{split}")
    owners = assign_stops(stops)
    reports: list[Report] = []
    for index in range(SIZES[split]):
        family = FAMILIES[index % len(FAMILIES)]
        reports.extend(build_report(index, split, family, stops, trips, rng, owners))
    return reports


def write(reports: list[Report], path: Path) -> str:
    lines = [
        json.dumps(report.__dict__, ensure_ascii=False, sort_keys=True)
        for report in reports
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode()).hexdigest()


def read(path: Path) -> list[Report]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return [
        Report(
            **{
                **row,
                "incidents": tuple(row["incidents"]),
                "parts": tuple(row["parts"]),
                "stops": tuple(row["stops"]),
            }
        )
        for row in rows
    ]
