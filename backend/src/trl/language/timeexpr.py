"""Read clock times, durations, dates and zones in Turkish and English reports.

All results are service-day seconds in the local zone. A report that names another day or an
unsupported zone is not read at all. The caller abstains.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

DAY = 86400
Role = Literal["from", "until", "bare"]
LOCAL_ZONE = r"(?:[+-]0?3(?::?00)?|trt|tsi|utc\s*\+\s*0?3(?::?00)?|gmt\s*\+\s*0?3(?::?00)?)"
OTHER_ZONE = re.compile(r"(?<![\w])(?:utc|gmt|zulu|z)(?![\w])|(?<=\d)\s*[+-]\d{2}:?\d{2}(?!\d)")
MONTHS = {
    "ocak": 1, "subat": 2, "mart": 3, "nisan": 4, "mayis": 5, "haziran": 6, "temmuz": 7,
    "agustos": 8, "eylul": 9, "ekim": 10, "kasim": 11, "aralik": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}  # fmt: skip
MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
ISO_DATETIME = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})(?:[t ](\d{2}):(\d{2})(?::\d{2})?(?:\.\d+)?"
    r"(?:\s*z|\s*[+-]\d{2}:?\d{2})?)?"
)
NUMERIC_DATE = re.compile(r"(?<![\d:.])(\d{1,2})[./](\d{1,2})[./](\d{4})(?![\d:])")
NAMED_DAY_FIRST = re.compile(rf"\b(\d{{1,2}})\s*(?:'|’)?\s*(?:inci|nci|uncu)?\s*({MONTH})\b")
NAMED_MONTH_FIRST = re.compile(rf"\b({MONTH})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b")
RELATIVE = re.compile(
    r"\b(?:tomorrow|yesterday|yarin|dun|haftaya|gelecek|next\s+\w+day|next week|"
    r"last\s+\w+day|gecen)\b"
)
CLOCK = re.compile(
    r"(?<![\w:.,+-])(\d{1,2})[:.]([0-5]\d)(?::[0-5]\d)?(?:\s*([ap])\.?m\.?)?(?![\w:]|[.,]\d)"
)
SAAT_HOUR = re.compile(r"\bsaat\s+(\d{1,2})(?![\d:.,])")
DURATION = re.compile(
    r"(?<![\w.,+-])(\d{1,3}(?:[.,]\d+)?)\s*(hours?|hrs?|saat|minutes?|mins?|dakika|dk|"
    r"seconds?|secs?|saniye|sn)\b"
)
HALF_HOUR = re.compile(r"\b(?:yarim saat|half an hour|half hour)\b")
FROM_BEFORE = re.compile(r"\b(?:from|since|after|starting|beginning|between)\s*$")
UNTIL_BEFORE = re.compile(r"\b(?:until|till|to|before|by|through)\s*$")
FROM_AFTER = re.compile(r"^(?:'|’)?(?:dan|den|tan|ten)\b|^\s*(?:itibaren|sonra|baslayarak)\b")
UNTIL_AFTER = re.compile(
    r"^(?:'|’)?(?:a|e|ya|ye)?\s*(?:kadar|dek)\b|^\s*(?:kadar|dek|oncesine kadar)\b"
)
RANGE_SEPARATOR = re.compile(r"^\s*(?:to|until|till|and|ile|ve|[-–—])\s*$")


@dataclass(frozen=True)
class Clock:
    seconds: int
    start: int
    end: int
    role: Role
    meridiem: str | None = None


@dataclass(frozen=True)
class Duration:
    seconds: int
    start: int
    end: int


@dataclass(frozen=True)
class TimeParse:
    clocks: tuple[Clock, ...] = ()
    start: Clock | None = None
    end: Clock | None = None
    durations: tuple[Duration, ...] = ()
    issues: tuple[str, ...] = ()
    notes: tuple[str, ...] = field(default=())


def blank(value: str, start: int, end: int) -> str:
    return value[:start] + " " * (end - start) + value[end:]


def read_dates(value: str, day: date) -> tuple[str, list[str]]:
    """Blank out dates that name the service day and report any that name another."""
    issues: list[str] = []

    def check(found: date | None, ambiguous: bool = False) -> None:
        if ambiguous:
            issues.append("ambiguous_date")
        elif found != day:
            issues.append("out_of_service_date")

    for match in list(ISO_DATETIME.finditer(value)):
        year, month, number = (int(match[i]) for i in (1, 2, 3))
        try:
            found: date | None = date(year, month, number)
        except ValueError:
            found = None
        check(found)
        hour, minute = match[4], match[5]
        keep = (match.start(4), match.end(5)) if hour else None
        value = blank(value, match.start(), match.end())
        if keep:
            value = (
                value[: keep[0]] + f"{hour}:{minute}" + value[keep[0] + len(f"{hour}:{minute}") :]
            )
    for match in list(NUMERIC_DATE.finditer(value)):
        first, second, year = (int(match[i]) for i in (1, 2, 3))
        readings: set[date] = set()
        for number, month in ((first, second), (second, first)):
            try:
                readings.add(date(year, month, number))
            except ValueError:
                continue
        ambiguous = len(readings) > 1 and day in readings and date(year, second, first) != day
        check(
            date(year, second, first) if 1 <= first <= 31 and 1 <= second <= 12 else None, ambiguous
        )
        value = blank(value, match.start(), match.end())
    for pattern, order in ((NAMED_DAY_FIRST, (1, 2)), (NAMED_MONTH_FIRST, (2, 1))):
        for match in list(pattern.finditer(value)):
            number, month = (
                int(match[order[0]]) if pattern is NAMED_DAY_FIRST else int(match[order[1]]),
                MONTHS[match[order[1]] if pattern is NAMED_DAY_FIRST else match[order[0]]],
            )
            try:
                found = date(day.year, month, number)
            except ValueError:
                found = None
            check(found)
            value = blank(value, match.start(), match.end())
    for match in list(RELATIVE.finditer(value)):
        issues.append("out_of_service_date")
        value = blank(value, match.start(), match.end())
    return value, issues


def read_zones(value: str) -> tuple[str, list[str]]:
    """Strip the local zone. Any other zone is unsupported."""
    local = re.compile(rf"(?<=\d)\s*{LOCAL_ZONE}(?![\w:])|\b(?:trt|tsi)\b")
    for match in list(local.finditer(value)):
        value = blank(value, match.start(), match.end())
    issues = ["unsupported_timezone"] if OTHER_ZONE.search(value) else []
    return value, issues


def read_durations(value: str) -> tuple[Duration, ...]:
    found: list[Duration] = []
    for match in HALF_HOUR.finditer(value):
        found.append(Duration(1800, match.start(), match.end()))
    for match in DURATION.finditer(value):
        unit = match[2]
        factor = (
            3600
            if unit.startswith(("h", "saat"))
            else 60
            if unit.startswith(("m", "dakika", "dk"))
            else 1
        )
        amount = round(float(match[1].replace(",", ".")) * factor)
        previous = found[-1] if found else None
        glue = (
            re.fullmatch(r"\s*(?:and|ve)?\s*", value[previous.end : match.start()])
            if previous
            else None
        )
        if previous and glue:
            found[-1] = Duration(previous.seconds + amount, previous.start, match.end())
        else:
            found.append(Duration(amount, match.start(), match.end()))
    return tuple(sorted(found, key=lambda item: item.start))


def hour_seconds(hour: int, minute: int, meridiem: str | None) -> int | None:
    if meridiem:
        if not 1 <= hour <= 12:
            return None
        hour = hour % 12 + (12 if meridiem == "p" else 0)
    return hour * 3600 + minute * 60 if hour <= 47 else None


def read_clocks(value: str, taken: list[Duration]) -> list[Clock]:
    raw: list[tuple[int, int, int, int, str | None]] = []
    for match in CLOCK.finditer(value):
        if any(item.start <= match.start() < item.end for item in taken):
            continue
        raw.append((int(match[1]), int(match[2]), match.start(), match.end(), match[3]))
    for match in SAAT_HOUR.finditer(value):
        if any(item.start <= match.start(1) < item.end for item in taken):
            continue
        raw.append((int(match[1]), 0, match.start(1), match.end(), None))
    clocks: list[Clock] = []
    for hour, minute, start, end, meridiem in sorted(raw, key=lambda item: item[2]):
        seconds = hour_seconds(hour, minute, meridiem)
        if seconds is None:
            continue
        before, after = value[:start], value[end:]
        role: Role = "bare"
        if FROM_AFTER.match(after) or FROM_BEFORE.search(before):
            role = "from"
        if UNTIL_AFTER.match(after) or UNTIL_BEFORE.search(before):
            role = "until"
        clocks.append(Clock(seconds, start, end, role, meridiem))
    return clocks


def carry_meridiem(first: Clock, second: Clock) -> tuple[Clock, Clock, str | None]:
    """Apply a lone am or pm on one side of a range to the other side when that reads sensibly."""
    if bool(first.meridiem) == bool(second.meridiem):
        return first, second, None
    marked, other = (second, first) if second.meridiem else (first, second)
    marker = marked.meridiem or "a"
    base = other.seconds
    carried = base % 43200 + (43200 if marker == "p" else 0) if base < 43200 else base
    plain = base
    low, high = (carried, marked.seconds) if marked is second else (marked.seconds, carried)
    plain_low, plain_high = (plain, marked.seconds) if marked is second else (marked.seconds, plain)
    carried_ok = 0 < high - low <= 43200
    plain_ok = 0 < plain_high - plain_low <= 43200
    if carried_ok and plain_ok and carried != plain:
        return first, second, "ambiguous_meridiem"
    if carried_ok:
        updated = Clock(carried, other.start, other.end, other.role, other.meridiem)
        return (first, updated, None) if marked is first else (updated, second, None)
    return first, second, None


def parse(value: str, day: date) -> TimeParse:
    """Parse folded text. Offsets in the result index into `value`."""
    issues: list[str] = []
    value, found = read_dates(value, day)
    issues += found
    value, found = read_zones(value)
    issues += found
    durations = read_durations(value)
    clocks = read_clocks(value, list(durations))
    if issues:
        return TimeParse(
            clocks=tuple(clocks), durations=durations, issues=tuple(dict.fromkeys(issues))
        )
    if len(clocks) > 2:
        return TimeParse(clocks=tuple(clocks), durations=durations, issues=("conflicting_times",))
    start = end = None
    if len(clocks) == 1:
        only = clocks[0]
        if only.role == "until":
            end = only
        else:
            start = only
    elif len(clocks) == 2:
        first, second = clocks
        separator = value[first.end : second.start]
        if first.role == "until" and second.role in {"from", "bare"}:
            start, end = second, first
        elif first.role == "from" or RANGE_SEPARATOR.match(separator) or second.role == "until":
            start, end = first, second
        elif first.role == "bare" and second.role == "bare":
            return TimeParse(clocks=tuple(clocks), durations=durations, issues=("unbound_times",))
        else:
            start, end = first, second
        if start is first and end is second:
            first, second, problem = carry_meridiem(first, second)
            if problem:
                return TimeParse(clocks=tuple(clocks), durations=durations, issues=(problem,))
            start, end = first, second
        if start and end and end.seconds <= start.seconds:
            gap = end.seconds + DAY - start.seconds
            if gap <= 43200:
                end = Clock(end.seconds + DAY, end.start, end.end, end.role, end.meridiem)
    return TimeParse(clocks=tuple(clocks), start=start, end=end, durations=durations)


def service_day_offset(day: date, other: date) -> int:
    return (other - day).days * DAY


__all__ = ["Clock", "Duration", "TimeParse", "parse", "service_day_offset", "timedelta"]
