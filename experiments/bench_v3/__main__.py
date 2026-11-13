# pyright: basic
"""Build, audit, run and report TRL-Bench v3.

python -m experiments.bench_v3 build
python -m experiments.bench_v3 audit
python -m experiments.bench_v3 run --split dev
python -m experiments.bench_v3 report --split dev
"""

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import TextIO

from experiments.bench_v3 import audit as auditing
from experiments.bench_v3 import catalogue, generate, runner, stats
from experiments.bench_v3.generate import SPLITS

ROOT = Path("data/bench/v3")
RESULTS = Path("experiments/results/v2/bench")
SEED = 20261114
CODE = [
    Path("experiments/bench_v3") / name
    for name in ("generate.py", "morph_tr.py", "catalogue.py")
]


def dataset(split: str) -> Path:
    return ROOT / f"{split}.jsonl"


def build() -> None:
    stops, trips, _ = catalogue.load()
    paths: dict[str, Path] = {}
    for split in SPLITS:
        reports = generate.build(split, stops, trips, SEED)
        generate.write(reports, dataset(split))
        paths[split] = dataset(split)
    auditing.write_manifest(ROOT / "FREEZE.json", auditing.manifest(paths, SEED, CODE))
    print(f"Wrote {len(paths)} splits.")


def check() -> int:
    stops, _, _ = catalogue.load()
    data = {split: generate.read(dataset(split)) for split in SPLITS}
    problems = auditing.audit(data, stops)
    frozen = json.loads((ROOT / "FREEZE.json").read_text())
    current = auditing.manifest({s: dataset(s) for s in SPLITS}, SEED, CODE)
    if current != frozen:
        problems.append("The dataset or generator differs from FREEZE.json.")
    for line in problems[:20]:
        print(line, file=sys.stderr)
    print(json.dumps({"problems": len(problems)}))
    return 1 if problems else 0


def require_frozen(split: str) -> None:
    if split == "test":
        plan = Path("docs/v2/preregistration.md")
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(plan)],
            capture_output=True,
            check=False,
        )
        if tracked.returncode != 0:
            raise SystemExit(
                "Commit docs/v2/preregistration.md before reading the test split."
            )
        if check() != 0:
            raise SystemExit("The audit failed. Fix it before reading the test split.")


def write_row(handle: TextIO, row: dict[str, object]) -> None:
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def run(split: str, arms: tuple[str, ...]) -> None:
    require_frozen(split)
    from trl.gtfs import load_schedule

    _, _, day = catalogue.load()
    schedule = load_schedule()
    RESULTS.mkdir(parents=True, exist_ok=True)
    target = RESULTS / f"{split}.jsonl"
    if target.exists():
        raise SystemExit(f"{target} exists. Results are written once per split.")
    with target.open("x") as handle:
        runner.run(
            generate.read(dataset(split)),
            schedule,
            day,
            arms,
            lambda row: write_row(handle, row),
        )


def report(split: str) -> None:
    rows = runner.load_rows(RESULTS / f"{split}.jsonl")
    arms = list(dict.fromkeys(str(row["arm"]) for row in rows))
    by_arm = {arm: {str(r["id"]): r for r in rows if r["arm"] == arm} for arm in arms}
    lines = [f"# TRL-Bench v3 · {split}", ""]
    lines += [
        "| Arm | Reports | Correct | 95% cluster interval | Unsupported | Unsupported upper bound |"
    ]
    lines += ["| --- | ---: | ---: | --- | ---: | ---: |"]
    for arm in arms:
        data = list(by_arm[arm].values())
        groups: dict[str, list[float]] = defaultdict(list)
        cluster_of: dict[str, str] = {}
        for row in data:
            groups[str(row["group"])].append(float(bool(row["correct"])))
            cluster_of[str(row["group"])] = str(row["cluster"])
        scores = [sum(v) / len(v) for v in groups.values()]
        centre, low, high = stats.cluster_bootstrap(
            scores, [cluster_of[g] for g in groups]
        )
        wrong = sum(bool(row["unsupported"]) for row in data)
        upper = stats.clopper_pearson(wrong, len(data))[1]
        correct = sum(bool(row["correct"]) for row in data)
        lines.append(
            f"| {arm} | {len(data)} | {correct} ({centre:.1%}) | [{low:.1%}, {high:.1%}] | {wrong} | {upper:.2%} |"
        )
    lines += ["", "## Paired contrasts (exact McNemar, Holm-adjusted)", ""]
    raw: dict[str, float] = {}
    counts: dict[str, tuple[int, int]] = {}
    for left in arms:
        for right in arms:
            if left >= right:
                continue
            a, b = by_arm[left], by_arm[right]
            only_left = sum(
                bool(a[k]["correct"]) and not bool(b[k]["correct"]) for k in a
            )
            only_right = sum(
                bool(b[k]["correct"]) and not bool(a[k]["correct"]) for k in a
            )
            name = f"{left} vs {right}"
            raw[name], counts[name] = (
                stats.mcnemar_exact(only_left, only_right),
                (only_left, only_right),
            )
    adjusted = stats.holm(raw)
    lines += [
        "| Contrast | Only left right | Only right right | p | Holm p |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for name, value in raw.items():
        left, right = counts[name]
        lines.append(
            f"| {name} | {left} | {right} | {value:.4f} | {adjusted[name]:.4f} |"
        )
    lines += ["", "## Accuracy by family", ""]
    families = sorted({str(r["family"]) for r in rows})
    lines += [
        "| Family | " + " | ".join(arms) + " |",
        "| --- | " + " | ".join("---:" for _ in arms) + " |",
    ]
    for family in families:
        cells = []
        for arm in arms:
            data = [r for r in by_arm[arm].values() if r["family"] == family]
            cells.append(f"{sum(bool(r['correct']) for r in data)}/{len(data)}")
        lines.append(f"| {family} | " + " | ".join(cells) + " |")
    (RESULTS / f"{split}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "audit", "run", "report"))
    parser.add_argument("--split", choices=SPLITS, default="dev")
    parser.add_argument("--arms", nargs="*", default=list(runner.ARMS))
    args = parser.parse_args()
    if args.command == "build":
        build()
    elif args.command == "audit":
        sys.exit(check())
    elif args.command == "run":
        run(args.split, tuple(args.arms))
    else:
        report(args.split)


if __name__ == "__main__":
    main()
