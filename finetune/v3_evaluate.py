"""Ask an Ollama model for a quote of every report and save the raw replies.

All arms run through the production path: Ollama structured output with the extraction schema,
temperature 0 and seed 42. Replies are appended one JSON line per report so a run can resume.
Requests run in parallel, so start Ollama with `OLLAMA_NUM_PARALLEL` at the worker count. The
benchmark runner reads the file as an external arm (`label=path`).
"""

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter

import httpx
from trl.vnext import Extraction, ollama_format

from finetune import rag

PROMPT = Path("backend/src/trl/prompts/operator_vnext.md")
PREREGISTRATION = Path("docs/v2/preregistration-operator-v3.md")
FIRST_DEV_EVAL_GROUP = 50
HOST = "http://127.0.0.1:11434"
# Families whose outcome depends on the model's quote (see the preregistration).
HARD = {
    "closure_range",
    "closure_until",
    "closure_from",
    "closure_note",
    "closure_pair",
    "ambiguous_stop",
    "negated",
    "hedged",
}


def selected(
    bench: str, split: str, limit: int | None, hard: bool, half: bool = False
) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in Path(f"data/bench/{bench}/{split}.jsonl").read_text().splitlines()
    ]
    if split == "dev":
        rows = [
            r
            for r in rows
            if int(str(r["group"]).split("-")[1]) >= FIRST_DEV_EVAL_GROUP
        ]
    if hard:
        rows = [r for r in rows if r["family"] in HARD]
    if half:  # a fixed subset, chosen before any test report is read
        rows = [r for r in rows if int(str(r["group"]).split("-")[1]) % 2 == 0]
    return rows[:limit] if limit else rows


def ask(client: httpx.Client, model: str, system: str, content: str) -> tuple[str, int]:
    """One structured reply and the number of prompt tokens used."""
    response = client.post(
        f"{HOST}/api/chat",
        json={
            "model": model,
            "stream": False,
            "think": False,
            "format": ollama_format(Extraction),
            "keep_alive": "30m",
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_ctx": 4096,
                "num_predict": 260,
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
        },
    )
    response.raise_for_status()
    body = response.json()
    return str(body["message"]["content"]), int(body.get("prompt_eval_count", 0))


def guard_test() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(PREREGISTRATION)],
        capture_output=True,
        check=False,
    )
    if tracked.returncode != 0:
        raise SystemExit(f"Commit {PREREGISTRATION} before reading the test split.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Ollama model tag")
    parser.add_argument("--prompt", type=Path, default=PROMPT)
    parser.add_argument("--bench", default="v31", choices=("v3", "v31"))
    parser.add_argument(
        "--split", choices=("dev", "calibration", "test"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--hard", action="store_true", help="only the hard slice")
    parser.add_argument("--half", action="store_true", help="even-numbered groups only")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--rag", type=int, default=0, help="retrieve this many train examples"
    )
    args = parser.parse_args()
    if args.split == "test":
        guard_test()
    system = args.prompt.read_text()
    retriever = (
        rag.build(Path(f"data/bench/{args.bench}/train.jsonl")) if args.rag else None
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = (
        {json.loads(line)["id"] for line in args.output.read_text().splitlines()}
        if args.output.exists()
        else set()
    )
    rows = [
        r
        for r in selected(args.bench, args.split, args.limit, args.hard, args.half)
        if r["id"] not in done
    ]

    def one(client: httpx.Client, row: dict[str, object]) -> dict[str, object]:
        started = perf_counter()
        text = str(row["text"])
        content = (
            rag.view(retriever, text, args.rag)
            if retriever
            else json.dumps({"notice": text}, ensure_ascii=False)
        )
        reply, tokens = ask(client, args.model, system, content)
        return {
            "id": row["id"],
            "reply": reply,
            "prompt_tokens": tokens,
            "seconds": round(perf_counter() - started, 3),
        }

    with (
        httpx.Client(timeout=300, trust_env=False) as client,
        ThreadPoolExecutor(max_workers=args.workers) as pool,
        args.output.open("a", encoding="utf-8") as handle,
    ):
        futures = [pool.submit(one, client, row) for row in rows]
        for count, future in enumerate(as_completed(futures), start=1):
            handle.write(json.dumps(future.result(), ensure_ascii=False) + "\n")
            handle.flush()
            if count % 50 == 0:
                print(f"{args.split} {count}/{len(rows)}", flush=True)


if __name__ == "__main__":
    main()
