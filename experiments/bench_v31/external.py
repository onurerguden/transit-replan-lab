# pyright: basic
"""Ask a model of another family for the test-owned phrase parts of TRL-Bench v3.1.

The system under test is a Qwen model, so the test wording comes from Llama. Candidates pass
deterministic filters: no digits, a bounded length, no production lexicon words, no overlap with
an authored part, no hedge or negation words in a positive predicate, and a hedge or negation
word in a negated or hedged one. Raw replies are kept in a private directory and only counts are
printed, so the maintainers never read the sealed wording while building the system.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

import httpx
from trl.intake import INDIRECT
from trl.language.clauses import HEDGE
from trl.notice import ACTIONS, normalize

from experiments.bench_v31 import banks

HOST = "http://127.0.0.1:11434"
SEED = 20261114
LEXICON = [*ACTIONS.values(), *INDIRECT.values()]
SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {"type": "string"}}},
    "required": ["items"],
}
PAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "singular": {"type": "string"},
                    "plural": {"type": "string"},
                },
                "required": ["singular", "plural"],
            },
        }
    },
    "required": ["items"],
}
ASKS = {
    "CLOSED": {
        "en": "Write {n} different short English verb phrases a transit operator could use to say that a "
        "station is shut and not serving passengers. Each completes the sentence 'The station ___.' "
        "Give a singular and a plural form, for example singular 'is shut', plural 'are shut'. "
        "Use varied wording. Do not use the words closed, closure, out of service, cancelled, late or delayed. "
        "Do not use not, no, never, might, may, or if.",
        "tr": "Bir toplu taşıma işletmesinin bir istasyonun yolcu almadığını ve hizmet vermediğini söylemek için "
        "kullanabileceği {n} farklı kısa Türkçe yüklem öbeği yaz. Her biri 'İstasyon ___.' cümlesini tamamlar. "
        "Tekil ve çoğul biçim ver (Türkçede ikisi aynı olabilir). Çeşitli ifadeler kullan. "
        "kapalı, kapat, kapa, iptal, gecik, değil, yok, olabilir, belki sözcüklerini kullanma.",
    },
    "LEADS": {
        "en": "Write {n} different very short announcement lead-ins a transit operator puts before a service message, "
        "such as 'Notice:'. Each ends with a colon.",
        "tr": "Bir toplu taşıma işletmesinin servis mesajının önüne koyduğu {n} farklı çok kısa duyuru girişi yaz, "
        "örneğin 'Duyuru:'. Her biri iki nokta ile biter.",
    },
    "CALM": {
        "en": "Write {n} different one-sentence notices saying that transit services are running as usual today. "
        "Do not mention delays, cancellations or closures.",
        "tr": "Bugün toplu taşıma seferlerinin her zamanki gibi sürdüğünü söyleyen {n} farklı tek cümlelik duyuru yaz. "
        "Gecikme, iptal ya da kapanıştan söz etme.",
    },
    "NOTES": {
        "en": "Write {n} different very short passenger information notes about station facilities that are not "
        "available, in the style '(no lifts)' or 'No parking is available.' Do not mention closures or delays.",
        "tr": "Bir istasyondaki mevcut olmayan olanaklar hakkında {n} farklı çok kısa yolcu notu yaz, "
        "örneğin '(asansör yok)'. Kapanış ya da gecikmeden söz etme.",
    },
    "NEGATED": {
        "en": "Write {n} different short English verb phrases that say a station is NOT shut, each completing "
        "'The station ___.' and each containing the word not. Example: 'is not shut'.",
        "tr": "Bir istasyonun kapalı OLMADIĞINI söyleyen {n} farklı kısa Türkçe yüklem öbeği yaz. "
        "Her birinde 'değil' sözcüğü geçsin. Örnek: 'kapalı değildir'.",
    },
    "HEDGED": {
        "en": "Write {n} different short English verb phrases that say a station MIGHT be shut but it is uncertain, "
        "each completing 'The station ___.' and each containing might, possibly or expected. "
        "Example: 'might be shut'.",
        "tr": "Bir istasyonun kapalı OLABİLECEĞİNİ ama kesin olmadığını söyleyen {n} farklı kısa Türkçe yüklem öbeği yaz. "
        "Her birinde olabilir, belki, muhtemelen ya da bekleniyor sözcüklerinden biri geçsin.",
    },
}
PAIRS = {"CLOSED"}
LIMITS = {"CLOSED": 18, "LEADS": 10, "CALM": 8, "NOTES": 8, "NEGATED": 10, "HEDGED": 10}
PLAIN = re.compile(r"^[^\W\d_]+(?:[ '\u2019\-][^\W\d_]+)*$")


def authored(name: str, lang: str) -> set[str]:
    rows = banks.globals_table(name, lang)
    return {normalize(str(row[2])) for row in rows}


def ask(client: httpx.Client, prompt: str, pairs: bool, seed: int) -> list[object]:
    response = client.post(
        f"{HOST}/api/chat",
        json={
            "model": "llama3.2:3b",
            "stream": False,
            "format": PAIR_SCHEMA if pairs else SCHEMA,
            "options": {
                "temperature": 0.8,
                "seed": seed,
                "num_ctx": 4096,
                "num_predict": 1500,
            },
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    response.raise_for_status()
    try:
        return json.loads(response.json()["message"]["content"]).get("items", [])
    except json.JSONDecodeError:
        return []  # a truncated reply counts as an attempt with no candidates


def acceptable(name: str, lang: str, text: str, taken: set[str]) -> bool:
    value = normalize(text)
    if not text or len(text) > 80 or re.search(r"\d", text) or value in taken:
        return False
    if name in {"CLOSED", "NEGATED", "HEDGED"} and any(
        value in t or t in value for t in taken
    ):
        return (
            False  # a phrase that contains or sits inside an authored phrase is not new
        )
    if name in {"CLOSED", "NEGATED", "HEDGED"} and not PLAIN.match(text):
        return False  # punctuation would split the clause around the quoted phrase
    words = len(text.split())
    if not (1 <= words <= (6 if name != "CALM" else 14)):
        return False
    if name == "LEADS" and not text.strip().endswith((":", ".")):
        return False
    lexical = any(rx.search(value) for rx in LEXICON)
    hedge = bool(HEDGE.search(value))
    if name == "CLOSED":
        return not lexical and not hedge
    if name in {"NEGATED", "HEDGED"}:
        return hedge
    return not lexical


def generate(
    seed: int = SEED,
) -> tuple[dict[str, dict[str, list[list[str]]]], dict[str, int]]:
    parts: dict[str, dict[str, list[list[str]]]] = {}
    counts: dict[str, int] = {}
    with httpx.Client(timeout=180, trust_env=False) as client:
        for name, languages in ASKS.items():
            parts[name] = {}
            for lang, template in languages.items():
                taken = authored(name, lang)
                picked: list[list[str]] = []
                raw: list[object] = []
                for attempt in range(6):
                    if len(picked) >= LIMITS[name]:
                        break
                    try:
                        items = ask(
                            client,
                            template.format(n=LIMITS[name] + 4),
                            name in PAIRS,
                            seed + attempt,
                        )
                    except httpx.TimeoutException:
                        continue
                    raw.extend(items)
                    for item in items:
                        single, plural = (
                            (item["singular"], item["plural"])
                            if isinstance(item, dict)
                            else (item, item)
                        )
                        single, plural = (
                            str(single).strip().rstrip("."),
                            str(plural).strip().rstrip("."),
                        )
                        if name == "LEADS":
                            single = plural = (
                                single
                                if single.endswith(":")
                                else single.rstrip(":") + ":"
                            )
                            single = plural = single + " "
                        if acceptable(name, lang, single, taken) and acceptable(
                            name, lang, plural, taken
                        ):
                            taken.add(normalize(single))
                            number = len(picked) + 1
                            row = [
                                f"{lang}-{name.lower()[:2]}-t{number}",
                                "test",
                                single,
                            ]
                            if name in PAIRS:
                                row.append(plural)
                            picked.append(row)
                            if len(picked) >= LIMITS[name]:
                                break
                (Path(".local/v31") / f"raw-{name}-{lang}.json").write_text(
                    json.dumps(raw, ensure_ascii=False), encoding="utf-8"
                )
                parts[name][lang] = picked
                counts[f"{name}/{lang}"] = len(picked)
    return parts, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=banks.SEALED)
    args = parser.parse_args()
    Path(".local/v31").mkdir(parents=True, exist_ok=True)
    parts, counts = generate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(parts, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(
        json.dumps(
            {"counts": counts, "sha256": hashlib.sha256(text.encode()).hexdigest()},
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
