"""Check local Qwen structured output with a synthetic closure notice."""

import argparse
import json
from typing import Literal, cast

import httpx
from pydantic import BaseModel, ConfigDict

MODEL = "qwen3.5:4b-q4_K_M"
CONTEXT = 4096


class Notice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["stop_closure"]
    target: Literal["Konak İskele"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    options = parser.parse_args()
    with httpx.Client(
        base_url=options.base_url, timeout=180.0, trust_env=False
    ) as client:
        version = client.get("/api/version")
        version.raise_for_status()
        tags = client.get("/api/tags")
        tags.raise_for_status()
        models = cast("list[dict[str, str]]", tags.json()["models"])
        model = next(item for item in models if item["name"] == MODEL)

        show = client.post("/api/show", json={"model": MODEL})
        show.raise_for_status()
        metadata = cast("dict[str, object]", show.json()["model_info"])
        contexts = {
            key: value
            for key, value in metadata.items()
            if key.endswith(".context_length")
        }

        response = client.post(
            "/api/chat",
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": "Return the event and exact stop name as JSON.",
                    },
                    {
                        "role": "user",
                        "content": "Konak İskele tramvay durağı geçici olarak kapatıldı.",
                    },
                ],
                "format": Notice.model_json_schema(),
                "stream": False,
                "think": False,
                "keep_alive": 0,
                "options": {"temperature": 0, "seed": 42, "num_ctx": CONTEXT},
            },
        )
        response.raise_for_status()
        completion = cast("str", response.json()["message"]["content"])
        notice = Notice.model_validate_json(completion)
        print(
            json.dumps(
                {
                    "ollama_version": version.json()["version"],
                    "model": MODEL,
                    "model_digest": model["digest"],
                    "model_contexts": contexts,
                    "configured_context": CONTEXT,
                    "validated_notice": notice.model_dump(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
