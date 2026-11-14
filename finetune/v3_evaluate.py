"""Ask an Ollama model for a quote of every report and save the raw replies.

All arms run through the production path: Ollama structured output with the extraction schema,
temperature 0 and seed 42. Replies are appended one JSON line per report so a run can resume.
The benchmark runner reads the file as an external arm (`label=path`).
"""

import argparse
import json
from pathlib import Path
from time import perf_counter

import httpx
from trl.vnext import Extraction

from finetune import rag

PROMPT = Path("backend/src/trl/prompts/operator_vnext.md")
FIRST_DEV_EVAL_GROUP = 50
HOST = "http://127.0.0.1:11434"


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


def ask(client: httpx.Client, model: str, system: str, content: str) -> tuple[str, int]:
    """One structured reply and the number of prompt tokens used."""
    response = client.post(
        f"{HOST}/api/chat",
        json={
            "model": model,
            "stream": False,
            "think": False,
            "format": Extraction.model_json_schema(),
            "keep_alive": "15m",
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Ollama model tag")
    parser.add_argument("--prompt", type=Path, default=PROMPT)
    parser.add_argument(
        "--split", choices=("dev", "calibration", "test"), required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--rag", type=int, default=0, help="retrieve this many train examples"
    )
    args = parser.parse_args()
    if args.split == "test":
        raise SystemExit(
            "The sealed test split is read only by the preregistered final run."
        )
    system = args.prompt.read_text()
    retriever = rag.build() if args.rag else None
    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = (
        {json.loads(line)["id"] for line in args.output.read_text().splitlines()}
        if args.output.exists()
        else set()
    )
    with (
        httpx.Client(timeout=120, trust_env=False) as client,
        args.output.open("a", encoding="utf-8") as handle,
    ):
        for count, row in enumerate(selected(args.split, args.limit), start=1):
            if row["id"] in done:
                continue
            started = perf_counter()
            text = str(row["text"])
            content = (
                rag.view(retriever, text, args.rag)
                if retriever
                else json.dumps({"notice": text}, ensure_ascii=False)
            )
            reply, tokens = ask(client, args.model, system, content)
            handle.write(
                json.dumps(
                    {
                        "id": row["id"],
                        "reply": reply,
                        "prompt_tokens": tokens,
                        "seconds": round(perf_counter() - started, 3),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            handle.flush()
            if count % 25 == 0:
                print(f"{args.split} {count}", flush=True)


if __name__ == "__main__":
    main()
