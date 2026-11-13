"""Ask the base model or the adapter for a quote of every report and save the raw replies.

Run it with the MLX environment. It reads the benchmark rows as plain JSON so it needs no
other package. Greedy decoding keeps the replies reproducible.
"""

import argparse
import json
from pathlib import Path
from time import perf_counter

from mlx_lm import generate, load

PROMPT = Path("backend/src/trl/prompts/operator_vnext.md")
FIRST_DEV_EVAL_GROUP = 50


def selected(split: str, limit: int | None) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in Path(f"data/bench/v3/{split}.jsonl").read_text().splitlines()
    ]
    if split == "dev":
        rows = [
            r
            for r in rows
            if int(str(r["group"]).split("-")[1]) >= FIRST_DEV_EVAL_GROUP
        ]
    return rows[:limit] if limit else rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, default=None)
    parser.add_argument(
        "--split", choices=("dev", "calibration", "test"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if args.split == "test" and not Path("docs/v2/preregistration-models.md").exists():
        raise SystemExit("Register the model arms before reading the test split.")
    prompt = PROMPT.read_text()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = (
        {json.loads(line)["id"] for line in args.output.read_text().splitlines()}
        if args.output.exists()
        else set()
    )
    model, tokenizer = load(
        str(args.model), adapter_path=str(args.adapter) if args.adapter else None
    )
    with args.output.open("a") as handle:
        for index, row in enumerate(selected(args.split, args.limit), start=1):
            if row["id"] in done:
                continue
            messages = [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps({"notice": row["text"]}, ensure_ascii=False),
                },
            ]
            text = tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            started = perf_counter()
            reply = generate(
                model, tokenizer, prompt=text, max_tokens=80, verbose=False
            )
            handle.write(
                json.dumps(
                    {
                        "id": row["id"],
                        "reply": reply,
                        "seconds": round(perf_counter() - started, 3),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            handle.flush()
            if index % 25 == 0:
                print(f"{args.split} {index}", flush=True)


if __name__ == "__main__":
    main()
