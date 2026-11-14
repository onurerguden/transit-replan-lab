"""Compare two files of raw Operator replies on the ids they share.

Used to check that a model exported to Ollama quotes what the MLX adapter quoted.
"""

import argparse
import json
from pathlib import Path

from trl.vnext import Extraction


def load(path: Path) -> dict[str, str]:
    return {
        row["id"]: row["reply"]
        for row in map(json.loads, path.read_text().splitlines())
    }


def quotes(reply: str) -> frozenset[tuple[str, str]] | None:
    """The kind quotes of a reply, or None when it is not a valid extraction."""
    try:
        extraction = Extraction.model_validate_json(reply.strip())
    except ValueError:
        return None
    return frozenset(
        (q.quote, str(q.kind)) for q in extraction.quotes if q.slot == "kind"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args()
    left, right = load(args.left), load(args.right)
    ids = sorted(set(left) & set(right))
    valid = {
        name: sum(quotes(r[i]) is not None for i in ids)
        for name, r in (("left", left), ("right", right))
    }
    same = sum(quotes(left[i]) == quotes(right[i]) for i in ids)
    print(
        json.dumps(
            {"shared": len(ids), "valid": valid, "identical_quotes": same}, indent=1
        )
    )


if __name__ == "__main__":
    main()
