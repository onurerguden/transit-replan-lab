# pyright: basic
"""Build TRL-Bench v3.1 reports from phrase parts that belong to exactly one split.

The structure follows v3 (see `experiments/bench_v3/generate.py`) with three differences. The
authored banks are larger so the train split teaches many ways to name an event. Sentence frames
that order the subject, predicate and time differently are split-owned parts, so test uses
constructions no other split uses. The predicate quoted as `kind_phrase` is the phrase in the
sentence, including the plural form for two-stop reports. The v3 files stay untouched.
"""

import random
from datetime import date

from experiments.bench_v3 import morph_tr
from experiments.bench_v3.generate import (
    APPLY,
    ASK,
    FAMILIES,
    SIZES,
    SPLITS,
    Action,
    Lang,
    Report,
    Split,
    assign_stops,
    clock,
    read,
    write,
)
from experiments.bench_v31 import banks

__all__ = ["SIZES", "SPLITS", "build", "read", "write"]


def choose(
    rows: list[tuple[str, ...]], split: str, rng: random.Random
) -> tuple[str, ...]:
    pool = [row for row in rows if row[1] == split]
    if not pool:
        raise ValueError(f"No parts for split {split}.")
    return rng.choice(pool)


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
    predicate = choose(banks.table("CLOSED", lang), split, rng)
    lead = choose(banks.table("LEADS", lang), split, rng)
    form = choose(banks.table("TIME_FORMS", lang), split, rng)
    frame = choose(banks.FRAMES, split, rng)
    a, b = clock(start), clock(end)
    name, other_name = stops[stop], stops[other]

    def times(a_text: str, b_text: str, template: str) -> str:
        return template.format(
            a=a_text, b=b_text,
            a_abl=morph_tr.clock_ablative(a) if lang == "tr" and a_text == a else a_text,
            b_dat=morph_tr.clock_dative(b) if lang == "tr" and b_text == b else b_text,
        )  # fmt: skip

    window = times(a, b, form[2])
    mode = stop.partition(":")[0]
    subject = (
        f"{name} {'tram stop' if mode == 'tram' else 'metro station'}"
        if lang == "en"
        else f"{name} {'tramvay durağı' if mode == 'tram' else 'metro istasyonu'}"
    )

    def sentence(lead_text: str, subj: str, phrase: str, when: str) -> str:
        return frame[2].format(lead=lead_text, S=subj, P=phrase, T=when)

    parts = [predicate[0], lead[0], form[0], frame[0]]
    action: Action = "apply"
    incidents: list[dict[str, object]] = []
    slot: str | None = None
    answer: str | None = None
    stops_used = (stop,)
    kind_phrase: str | None = predicate[2]
    closure = {"kind": "stop_closure", "stop": stop, "start": start, "end": end}
    if family == "closure_range":
        text, incidents = sentence(lead[2], subject, predicate[2], window), [closure]
    elif family == "closure_note":
        note = choose(banks.table("NOTES", lang), split, rng)
        text = f"{sentence(lead[2], subject, predicate[2], window)} {note[2]}"
        incidents, parts = [closure], [*parts, note[0]]
    elif family == "closure_pair":
        joiner = "and" if lang == "en" else "ve"
        both_tram = mode == "tram" and other.partition(":")[0] == "tram"
        noun = (
            ("tram stops" if both_tram else "stops")
            if lang == "en"
            else ("tramvay durakları" if both_tram else "durakları")
        )
        text = sentence(
            lead[2], f"{name} {joiner} {other_name} {noun}", predicate[3], window
        )
        incidents = [closure, {**closure, "stop": other}]
        stops_used, kind_phrase = (stop, other), predicate[3]
    elif family in {"closure_until", "closure_from"}:
        action, slot = "ask", "start" if family == "closure_until" else "end"
        open_form = choose(
            banks.table("UNTIL" if slot == "start" else "FROM", lang), split, rng
        )
        parts.append(open_form[0])
        phrase = times(a, b, open_form[2])
        text = (
            f"{lead[2]}{subject} {predicate[2]} {phrase}."
            if lang == "en"
            else f"{lead[2]}{subject} {phrase} {predicate[2]}."
        )
        answer = a if slot == "start" else b
        incidents = [closure]
    elif family == "ambiguous_stop":
        action, slot = "ask", "target"
        text = sentence(lead[2], "Konak", predicate[2], window)
        answer = "Konak İskele tram" if lang == "en" else "Konak İskele tramvay"
        incidents = [
            {"kind": "stop_closure", "stop": "tram:7", "start": start, "end": end}
        ]
        stops_used = ("tram:7",)
    elif family == "delay":
        word = "late" if lang == "en" else "gecikmeli"
        text = (
            f"{lead[2]}Trip {trip} is {minutes} minutes {word}."
            if lang == "en"
            else f"{lead[2]}{trip} seferi {minutes} dakika {word}."
        )
        incidents = [{"kind": "trip_delay", "trip": trip, "seconds": minutes * 60}]
        stops_used, kind_phrase = (), word
    elif family == "cancellation":
        text = (
            f"{lead[2]}Trip {trip} is cancelled."
            if lang == "en"
            else f"{lead[2]}{trip} seferi iptal edilmiştir."
        )
        incidents = [{"kind": "trip_cancellation", "trip": trip}]
        stops_used, kind_phrase = (), "cancelled" if lang == "en" else "iptal"
    elif family in {"negated", "hedged"}:
        action, incidents = "abstain", []
        phrase = choose(
            banks.table("NEGATED" if family == "negated" else "HEDGED", lang),
            split,
            rng,
        )
        parts.append(phrase[0])
        text = sentence(lead[2], subject, phrase[2], window)
        kind_phrase = phrase[2]
    elif family == "wrong_date":
        action, incidents = "abstain", []
        other_day = date(2026, 11, 3 + rng.randrange(20))
        label = (
            other_day.isoformat() if lang == "en" else other_day.strftime("%d.%m.%Y")
        )
        prefix = choose(banks.table("DATES", lang), split, rng)
        parts.append(prefix[0])
        text = f"{lead[2]}{prefix[2].format(d=label)}{sentence('', subject, predicate[2], window)}"
    elif family == "foreign_zone":
        action, incidents = "abstain", []
        plain = [
            f
            for f in banks.table("TIME_FORMS", lang)
            if f[1] == split and "_" not in f[2]
        ]
        zone = rng.choice(plain)
        parts[2] = zone[0]
        text = sentence(
            lead[2], subject, predicate[2], zone[2].format(a=f"{a} UTC", b=f"{b} UTC")
        )
    else:
        action, incidents, kind_phrase = "abstain", [], None
        calm = choose(banks.table("CALM", lang), split, rng)
        parts.append(calm[0])
        text = f"{lead[2]}{calm[2]}"
    return Report(
        f"{group}-{lang}", group, split, lang, family, text, action, tuple(incidents), slot,
        answer, tuple(parts), stops_used, kind_phrase if family in APPLY | ASK | {"negated", "hedged"} else None,
    )  # fmt: skip


def build(
    split: Split, stops: dict[str, str], trips: list[str], seed: int
) -> list[Report]:
    rng = random.Random(f"v31:{seed}:{split}")
    owners = assign_stops(stops)
    allowed = [stop for stop in stops if owners[stop] == split]
    reports: list[Report] = []
    for index in range(SIZES[split]):
        family = FAMILIES[index % len(FAMILIES)]
        start = rng.randrange(6 * 3600, 20 * 3600, 60)
        end = start + rng.randrange(20, 240, 5) * 60
        stop = rng.choice(allowed)
        other = rng.choice([item for item in allowed if item != stop])
        trip = rng.choice(trips)
        minutes = rng.randrange(3, 55)
        group = f"{split}-{index:05d}"
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
