# pyright: basic
"""Build, audit, run and report TRL-Bench v3.1 with the v3 runner and statistics.

python -m experiments.bench_v31 build
python -m experiments.bench_v31 audit
python -m experiments.bench_v31 run --split dev
python -m experiments.bench_v31 report --split dev
"""

import hashlib
import subprocess
from pathlib import Path

from experiments.bench_v3 import __main__ as cli
from experiments.bench_v31 import audit as audit31
from experiments.bench_v31 import banks, generate

ROOT = Path("data/bench/v31")
PREREGISTRATION = Path("docs/v2/preregistration-operator-v3.md")
CODE = [
    Path("experiments/bench_v31") / name for name in ("banks.py", "generate.py")
] + [
    Path("experiments/bench_v3/morph_tr.py"),
    Path("experiments/bench_v3/catalogue.py"),
]


def require_frozen(split: str) -> None:
    if split == "test":
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(PREREGISTRATION)],
            capture_output=True,
            check=False,
        )
        if tracked.returncode != 0:
            raise SystemExit(f"Commit {PREREGISTRATION} before reading the test split.")
        if cli.check() != 0:
            raise SystemExit("The audit failed. Fix it before reading the test split.")


def manifest(paths: dict[str, Path], seed: int, code: list[Path]) -> dict[str, object]:
    content = audit31.base.manifest(paths, seed, code)
    sealed = banks.SEALED.read_bytes() if banks.SEALED.exists() else b""
    content["sealed_parts"] = hashlib.sha256(sealed).hexdigest()
    return content


def main() -> None:
    cli.ROOT = ROOT
    cli.RESULTS = Path("experiments/results/v2_1/bench")
    cli.CODE = CODE
    cli.generate = generate
    cli.require_frozen = require_frozen
    cli.auditing = type(
        "Auditing",
        (),
        {
            "audit": staticmethod(audit31.audit),
            "manifest": staticmethod(manifest),
            "write_manifest": staticmethod(audit31.base.write_manifest),
        },
    )
    cli.main()


if __name__ == "__main__":
    main()
