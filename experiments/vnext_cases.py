"""Generate and audit bilingual benchmark partitions before opening model predictions."""

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Literal

from trl.disruptions import Overlay
from trl.domain import Disruption, Record, StopClosure, TripCancellation, TripDelay
from trl.gtfs import Schedule, load_schedule
from trl.routing import find_offers
from trl.scenarios import load_scenario
from trl.verify import check_plan
from trl.vnext import Slot

PARTITIONS = {"dev": 80, "calibration": 60, "locked": 120}
FAMILIES = (
    "canonical",
    "paraphrase",
    "target",
    "clock_or_delay",
    "conflict",
    "unknown",
)
ROOT = Path(".local/vnext-benchmark")


class GoldSpan(Record):
    slot: Slot
    start: int
    end: int
    quote: str


class Case(Record):
    id: str
    group: str
    family: str
    language: Literal["tr", "en"]
    notice: str
    incident: Disruption | None
    initial_action: Literal["apply", "ask", "abstain"]
    question_slot: Slot | None = None
    answer: str | None = None
    spans: tuple[GoldSpan, ...] = ()
    tight_window: bool = False
    expected_plan_status: Literal["feasible", "infeasible", "abstained"]


def clock(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}"


def make_case(
    split: str,
    index: int,
    serial: int,
    trip: str,
    day: str,
) -> Case:
    family = FAMILIES[index // 2 % len(FAMILIES)]
    tr = index % 2 == 0
    start = (8 * 60 + 10 + serial % 32) * 60
    end = (9 * 60 + 45 + serial // 32) * 60
    left, right = clock(start), clock(end)
    subtype = serial // len(FAMILIES)
    stop, target = (
        ("Konak İskele", "tram:7"),
        ("Karataş", "tram:8"),
        ("Alsancak Gar", "tram:3"),
    )[subtype % 3]
    other = "Karataş" if target != "tram:8" else "Konak İskele"
    before, after = (stop, other) if subtype % 2 else (other, stop)
    incident: Disruption | None = StopClosure(stop=target, start=start, end=end)
    expected: Literal["apply", "ask", "abstain"] = "apply"
    question: Slot | None = None
    answer = None
    kind = "kapalı" if tr else "closed"
    fields: list[tuple[Slot, str]] = [
        ("kind", kind),
        ("target", stop),
        ("start", left),
        ("end", right),
    ]
    if family == "canonical":
        notice = {
            "dev": f"{stop} tramvay durağı {left} ile {right} arasında {kind}."
            if tr
            else f"{stop} tram stop is {kind} from {left} to {right}.",
            "calibration": f"Tramvay bildirimi. {stop} {left}-{right} arasında {kind}."
            if tr
            else f"Tram bulletin. {stop} {kind} {left}-{right}.",
            "locked": f"{left} ile {right} arasında {stop} tramvay durağı {kind}."
            if tr
            else f"From {left} to {right}, {stop} tram stop is {kind}.",
        }[split]
    elif family == "paraphrase":
        kind = (
            ("giriş çıkış yok" if split == "dev" else "erişime ara verildi")
            if tr
            else "out of service"
        )
        notice = {
            "dev": f"{stop} tramvay durağında {left} ile {right} arasında {kind}."
            if tr
            else f"The {stop} tram platform is {kind} from {left} to {right}.",
            "calibration": f"{left} ile {right} arasında {stop} tramvay durağında {kind}."
            if tr
            else f"From {left} to {right}, the {stop} tram platform is {kind}.",
            "locked": f"{stop} tramvay durağında {left}-{right} aralığında {kind}."
            if tr
            else f"{stop} tram is {kind}, {left}-{right}.",
        }[split]
        fields[0] = "kind", kind
    elif family == "target":
        expected, question, answer = "ask", "target", target
        notice = {
            "dev": f"{before} veya {after} tramvay durağı {left} ile {right} arasında {kind}."
            if tr
            else f"{before} or {after} tram stop is {kind} from {left} to {right}.",
            "calibration": f"{left}-{right} arası {before} veya {after} tramvay durağı {kind}."
            if tr
            else f"From {left} to {right} either {before} or {after} tram stop is {kind}.",
            "locked": f"{before} ya da {after} tramvay durağı için {left}-{right} arası {kind}."
            if tr
            else f"Tram notice for {before} or {after}, {kind} {left}-{right}.",
        }[split]
    elif family == "clock_or_delay":
        if subtype % 3 == 0:
            kind = "gecikiyor" if tr else "delayed"
            amount = (
                f"{serial % 7 + 3} dakika 30 saniye"
                if tr
                else f"{serial % 7 + 3} minutes and 30 seconds"
            )
            incident = TripDelay(
                trip=trip,
                service_date=date.fromisoformat(day),
                seconds=(serial % 7 + 3) * 60 + 30,
            )
            notice = {
                "dev": f"{trip} seferi {amount} {kind}."
                if tr
                else f"Trip {trip} is {kind} by {amount}.",
                "calibration": f"{kind}: {amount}, sefer {trip}."
                if tr
                else f"{kind} trip {trip} by {amount}.",
                "locked": f"{amount} {kind}, tramvay seferi {trip}."
                if tr
                else f"By {amount}, trip {trip} is {kind}.",
            }[split]
            fields = [("kind", kind), ("target", trip), ("delay", amount)]
        elif subtype % 3 == 1:
            kind = "iptal" if tr else "cancelled"
            incident = TripCancellation(trip=trip, service_date=date.fromisoformat(day))
            notice = {
                "dev": f"{trip} seferi {kind} edildi."
                if tr
                else f"Trip {trip} is {kind}.",
                "calibration": f"{kind} edilen sefer {trip}."
                if tr
                else f"{kind} from today's service: trip {trip}.",
                "locked": f"Sefer bildirimi {trip}, {kind}."
                if tr
                else f"Timetable update, {trip} was {kind}.",
            }[split]
            fields = [("kind", kind), ("target", trip)]
        else:
            suffix = " a.m." if split == "locked" else " AM"
            left, right = left + suffix, right + suffix
            notice = {
                "dev": f"{stop} {left} ile {right} arasında {kind}."
                if tr
                else f"{stop} is {kind} between {left} and {right}.",
                "calibration": f"{left}-{right} arası {stop} {kind}."
                if tr
                else f"Platform {stop} is {kind} from {left} to {right}.",
                "locked": f"Tramvay bildirimi, {stop} {kind}: {left}-{right}."
                if tr
                else f"{left} to {right}, the {stop} tram platform is {kind}.",
            }[split]
            fields[-2:] = [("start", left), ("end", right)]
    elif family == "conflict":
        incident, expected, fields = None, "abstain", []
        notice = {
            "dev": f"{stop} {left} ile {right} arasında kapalı değil."
            if tr
            else f"{stop} tram is not closed from {left} to {right}.",
            "calibration": f"Belki {stop} {left}-{right} arası kapalı."
            if tr
            else f"Possibly closed at {stop} from {left} to {right}.",
            "locked": f"{left} ile {right} arasında {stop} kapalı mı?"
            if tr
            else f"Is {stop} closed between {left} and {right}?",
        }[split]
    else:
        incident, expected, question, answer = None, "ask", "end", "unknown"
        notice = {
            "dev": f"{stop} tramvay durağı {left} itibarıyla kapalı."
            if tr
            else f"{stop} tram stop is closed starting at {left}.",
            "calibration": f"{left} sonrasında {stop} durağı kapalı."
            if tr
            else f"From {left}, the {stop} tram platform is closed.",
            "locked": f"Tramvay duyurusu {stop}, {left} sonrası kapalı."
            if tr
            else f"Closure at {stop}. Start: {left}.",
        }[split]
        if not tr and split == "locked":
            fields[0] = "kind", "Closure"
        fields = fields[:-1]
    spans = tuple(
        GoldSpan(
            slot=slot,
            start=notice.index(value),
            end=notice.index(value) + len(value),
            quote=value,
        )
        for slot, value in fields
    )
    return Case(
        id=f"{split}-{index:03d}",
        group=f"event-{serial:03d}",
        family=family,
        language="tr" if tr else "en",
        notice=notice,
        incident=incident,
        initial_action=expected,
        question_slot=question,
        answer=answer,
        spans=spans,
        tight_window=serial % 13 == 0,
        expected_plan_status="abstained" if incident is None else "infeasible",
    )


def reference(
    schedule: Schedule, case: Case
) -> Literal["feasible", "infeasible", "abstained"]:
    if case.incident is None:
        return "abstained"
    scenario = load_scenario("infeasible" if case.tight_window else "demo")
    overlay = Overlay.compile((case.incident,))
    offers = find_offers(schedule, scenario, 1, overlay, limit=1)
    if not offers:
        return "infeasible"
    if check_plan(schedule, scenario, offers[0], overlay):
        raise ValueError(f"Independent feasibility check failed for {case.id}.")
    return "feasible"


def write(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    schedule = load_schedule()
    day = load_scenario().service_date
    scenario = load_scenario()
    trips = tuple(
        item.id
        for item in schedule.trips.values()
        if schedule.runs(item.service, day)
        and item.calls[0].departure <= scenario.meeting_end
        and item.calls[-1].arrival >= min(scenario.a.ready, scenario.b.ready)
    )
    offset = 0
    manifest: dict[str, str] = {}
    for split, count in PARTITIONS.items():
        cases: list[Case] = []
        for index in range(0, count, 2):
            serial = offset + index // 2
            pair = [
                make_case(
                    split,
                    index + i,
                    serial,
                    trips[serial % len(trips)],
                    day.isoformat(),
                )
                for i in range(2)
            ]
            status = reference(schedule, pair[0])
            cases.extend(
                item.model_copy(update={"expected_plan_status": status})
                for item in pair
            )
        payload = "".join(case.model_dump_json() + "\n" for case in cases).encode()
        (root / f"{split}.jsonl").write_bytes(payload)
        manifest[split] = hashlib.sha256(payload).hexdigest()
        offset += count // 2
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )


def read(root: Path, split: str) -> list[Case]:
    manifest = json.loads((root / "manifest.json").read_text())
    payload = (root / f"{split}.jsonl").read_bytes()
    if hashlib.sha256(payload).hexdigest() != manifest[split]:
        raise ValueError(f"{split} benchmark checksum mismatch.")
    return [Case.model_validate_json(line) for line in payload.splitlines()]


def template_signature(notice: str) -> str:
    value = notice.casefold()
    for name in ("konak i̇skele", "karataş", "alsancak gar"):
        value = value.replace(name, "<stop>")
    value = re.sub(r"(?:metro|tram):[\w-]+", "<trip>", value)
    value = re.sub(r"\b\d+(?::\d+)?\b", "<number>", value)
    return re.sub(r"\s+", " ", value).strip()


def audit(root: Path) -> None:
    schedule = load_schedule()
    day = load_scenario().service_date
    seen: set[str] = set()
    signatures: set[str] = set()
    for split, size in PARTITIONS.items():
        data = read(root, split)
        groups = {item.group for item in data}
        if len(data) != size or len(groups) != size // 2 or groups & seen:
            raise ValueError(f"Invalid partition or semantic-group leakage in {split}.")
        seen.update(groups)
        masked = {template_signature(item.notice) for item in data}
        if signatures & masked:
            raise ValueError(f"Masked template leakage into {split}.")
        signatures.update(masked)
        paired = {
            group: [item for item in data if item.group == group] for group in groups
        }
        for pair in paired.values():
            if {item.language for item in pair} != {"tr", "en"} or pair[
                0
            ].incident != pair[1].incident:
                raise ValueError("A bilingual pair has incompatible gold labels.")
        for case in data:
            for span in case.spans:
                if case.notice[span.start : span.end] != span.quote:
                    raise ValueError(f"Invalid evidence span in {case.id}.")
            event = case.incident
            if event is None:
                continue
            if event.kind == "stop_closure":
                if event.stop not in schedule.stops:
                    raise ValueError(f"Unknown stop in {case.id}.")
            elif event.trip not in schedule.trips or not schedule.runs(
                schedule.trips[event.trip].service,
                day,
            ):
                raise ValueError(f"Inactive service in {case.id}.")


if __name__ == "__main__":
    write(ROOT)
    audit(ROOT)
