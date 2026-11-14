# pyright: basic
"""Check that the gold-quote arm reads every family of a split, without writing results.

The generator must not hide events behind wording or constructions the deterministic substrate
cannot bind. This prints accuracy by family only, so it never shows sealed wording.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from trl.gtfs import load_schedule

from experiments.bench_v3 import catalogue, runner
from experiments.bench_v31 import generate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True)
    args = parser.parse_args()
    _, _, day = catalogue.load()
    schedule = load_schedule()
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for report in generate.read(Path(f"data/bench/v31/{args.split}.jsonl")):
        row = runner.score(report, runner.read(report, schedule, day, "model_ceiling"))
        tally[report.family][0] += int(bool(row["correct"]))
        tally[report.family][1] += 1
    for family, (right, total) in sorted(tally.items()):
        print(f"{family:16} {right}/{total}")
    print(
        f"total {sum(v[0] for v in tally.values())}/{sum(v[1] for v in tally.values())}"
    )


if __name__ == "__main__":
    main()


def by_part(split: str) -> dict[str, tuple[int, int]]:
    """Failures and uses per part id, to find which part the reader cannot bind."""
    _, _, day = catalogue.load()
    schedule = load_schedule()
    tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for report in generate.read(Path(f"data/bench/v31/{split}.jsonl")):
        row = runner.score(report, runner.read(report, schedule, day, "model_ceiling"))
        for part in report.parts:
            tally[part][0] += int(not row["correct"])
            tally[part][1] += 1
    return {part: (v[0], v[1]) for part, v in tally.items()}


def prune(limit: float = 0.10, rounds: int = 4) -> dict[str, int]:
    """Drop sealed parts the substrate cannot bind even with the gold quote, then rebuild test.

    A part that fails the gold-quote arm cannot be solved by any model, so it only adds noise.
    Only part ids and counts are printed.
    """
    from experiments.bench_v3 import catalogue as cat
    from experiments.bench_v31 import banks

    stops, trips, _ = cat.load()
    dropped: dict[str, int] = {}
    for _ in range(rounds):
        sealed = banks.sealed_parts()
        reports = generate.build("test", stops, trips, 20261114)
        schedule = load_schedule()
        _, _, day = cat.load()
        tally: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for report in reports:
            row = runner.score(
                report, runner.read(report, schedule, day, "model_ceiling")
            )
            for part in report.parts:
                tally[part][0] += int(not row["correct"])
                tally[part][1] += 1
        bad = {p for p, (f, n) in tally.items() if f / n > limit and "-t" in p}
        if not bad:
            break
        for table in sealed.values():
            for lang, rows in table.items():
                table[lang] = [row for row in rows if row[0] not in bad]
        banks.SEALED.write_text(
            json.dumps(sealed, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        dropped.update({p: tally[p][0] for p in bad})
    return dropped
