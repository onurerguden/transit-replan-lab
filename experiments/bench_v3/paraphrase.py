# pyright: basic
"""Rewrite test reports with a model from another family, keeping every fact as a placeholder.

The rewriting model never sees stop names, times, trip identifiers, dates or delays: they are
replaced by tokens, the model must return each token exactly once, and the original values are
put back. A rewrite that drops or repeats a token, adds a digit, repeats the original or
answers in the wrong language is discarded. Raw replies are kept.
"""

import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import httpx

from experiments.bench_v3 import catalogue, generate
from experiments.bench_v3.generate import Report

MODEL = "llama3.2:3b"
GROUPS = 300
TOKEN = re.compile(r"⟦[A-Z_0-9]+⟧")
CLOCK = re.compile(r"\b\d{2}:\d{2}\b")
TRIP = re.compile(r"\b(?:metro|tram):[\w-]+")
COUNT = re.compile(r"\b\d+(?= (?:minutes|dakika)\b)")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}\.\d{2}\.\d{4}\b")
TURKISH = set("çğıöşüİ")
SYSTEM = {
    "en": "Rewrite the sentence in English with different wording. Keep every token in double "
    "square brackets such as ⟦STOP_1⟧ exactly once and unchanged. Do not add numbers, names or "
    "places. Keep the meaning, including any negation, doubt and what is affected. Output only "
    "the rewritten sentence.",
    "tr": "Cümleyi Türkçe olarak farklı sözcüklerle yeniden yaz. ⟦STOP_1⟧ gibi çift köşeli "
    "ayraç içindeki her belirteci değiştirmeden ve tam bir kez koru. Sayı, ad veya yer ekleme. "
    "Olumsuzluk, belirsizlik ve neyin etkilendiği dahil anlamı koru. Yalnızca yeniden yazılmış "
    "cümleyi yaz.",
}


def delexicalize(report: Report, names: dict[str, str]) -> tuple[str, dict[str, str]]:
    values: dict[str, str] = {}
    text = report.text
    for number, stop in enumerate(report.stops, start=1):
        if (name := names.get(stop)) and name in text:
            text = text.replace(name, f"⟦STOP_{number}⟧", 1)
            values[f"⟦STOP_{number}⟧"] = name
    for pattern, label in ((DATE, "DATE"), (TRIP, "TRIP"), (COUNT, "COUNT")):
        for number, match in enumerate(dict.fromkeys(pattern.findall(text)), start=1):
            token = f"⟦{label}_{number}⟧"
            text = text.replace(match, token, 1)
            values[token] = match
    for number, match in enumerate(dict.fromkeys(CLOCK.findall(text)), start=1):
        token = f"⟦TIME_{number}⟧"
        text = text.replace(match, token)
        values[token] = match
    return text, values


def accept(original: str, rewrite: str, values: dict[str, str], lang: str) -> bool:
    tokens = Counter(TOKEN.findall(rewrite))
    if tokens != Counter(dict.fromkeys(values, 1)) or re.search(
        r"\d", TOKEN.sub("", rewrite)
    ):
        return False
    plain = TOKEN.sub("", rewrite)
    if not 12 <= len(plain) <= 300 or "\n" in rewrite.strip():
        return False
    turkish = bool(TURKISH & set(plain))
    if (lang == "en" and turkish) or (
        lang == "tr" and not turkish and " ve " not in plain
    ):
        return False
    return rewrite.strip().lower() != original.lower()


def relexicalize(rewrite: str, values: dict[str, str]) -> str:
    for token, value in values.items():
        rewrite = rewrite.replace(token, value)
    return rewrite


def ask(client: httpx.Client, lang: str, text: str, seed: int) -> str:
    response = client.post(
        "/api/chat",
        json={
            "model": MODEL,
            "stream": False,
            "options": {"temperature": 0.7, "seed": seed, "num_predict": 120},
            "messages": [
                {"role": "system", "content": SYSTEM[lang]},
                {"role": "user", "content": text},
            ],
        },
        timeout=120,
    )
    response.raise_for_status()
    return str(response.json()["message"]["content"]).strip().strip('"')


def main() -> None:
    stops, _, _ = catalogue.load()
    names = dict(stops)
    source = [r for r in generate.read(Path("data/bench/v3/test.jsonl"))]
    wanted = {f"test-{index:05d}" for index in range(GROUPS)}
    rows = [r for r in source if r.group in wanted]
    out: list[Report] = []
    raw: list[dict[str, object]] = []
    kept = Counter()
    with httpx.Client(base_url="http://127.0.0.1:11434") as client:
        info = client.get("/api/tags").json()["models"]
        digest = next(m["digest"] for m in info if m["name"] == MODEL)
        for report in rows:
            text, values = delexicalize(report, names)
            if not TOKEN.search(text):
                continue
            for attempt in range(3):
                seed = int(
                    hashlib.sha256(f"{report.id}:{attempt}".encode()).hexdigest()[:8],
                    16,
                )
                reply = ask(client, report.lang, text, seed)
                raw.append(
                    {
                        "id": report.id,
                        "attempt": attempt,
                        "prompt": text,
                        "reply": reply,
                    }
                )
                if accept(text, reply, values, report.lang):
                    final = relexicalize(reply, values)
                    out.append(
                        replace(
                            report,
                            id=report.id.replace("test-", "testp-"),
                            group=report.group.replace("test-", "testp-"),
                            text=final,
                            parts=(f"para:{MODEL}",),
                        )
                    )
                    kept["kept"] += 1
                    break
            else:
                kept["dropped"] += 1
    complete = {r.group for r in out}
    paired = [r for r in out if sum(x.group == r.group for x in out) == 2]
    del complete
    Path("data/bench/v3").mkdir(parents=True, exist_ok=True)
    digest_out = generate.write(paired, Path("data/bench/v3/paraphrase.jsonl"))
    Path("data/bench/v3/paraphrase-raw.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in raw) + "\n"
    )
    Path("data/bench/v3/PARAPHRASE.json").write_text(
        json.dumps(
            {
                "model": MODEL,
                "model_digest": digest,
                "groups_requested": GROUPS,
                "reports_kept": len(paired),
                "reports_dropped": kept["dropped"],
                "sha256": digest_out,
                "raw_sha256": hashlib.sha256(
                    Path("data/bench/v3/paraphrase-raw.jsonl").read_bytes()
                ).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )
    print(dict(kept), len(paired), file=sys.stderr)


if __name__ == "__main__":
    main()
