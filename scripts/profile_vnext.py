"""Measure the canonical vNext command-to-verified latency through the HTTP API."""

import argparse
import json
import platform
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter, sleep

from fastapi.testclient import TestClient
from trl.api.app import create_app
from trl.scenarios import load_scenario

from experiments.report import percentile
from experiments.vnext_runner import code_digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    elapsed: list[float] = []
    notice = load_scenario().notice
    with (
        TemporaryDirectory() as workspace,
        TestClient(create_app(Path(workspace) / "profile.sqlite")) as client,
    ):
        for number in range(15):
            created = client.post(
                "/v1/runs",
                json={"workflow": "vnext", "operator_mode": "rules"},
                headers={"Idempotency-Key": f"profile-{number}"},
            )
            created.raise_for_status()
            endpoint = f"/v1/runs/{created.json()['run_id']}"
            start = perf_counter()
            command = client.post(
                f"{endpoint}/disruptions",
                json={"version": 0, "notice": notice},
                headers={"Idempotency-Key": "incident"},
            )
            command.raise_for_status()
            for _ in range(400):
                outcome = client.get(endpoint)
                outcome.raise_for_status()
                result = outcome.json()
                if result["status"] != "planning":
                    break
                sleep(0.01)
            else:
                raise TimeoutError("The profile run did not reach a terminal state.")
            assert result["status"] == "verified" and result["metrics"]["calls"] == 0
            elapsed.append((perf_counter() - start) * 1000)
    options.output.write_text(
        json.dumps(
            {
                "source_digest": code_digest(),
                "system": platform.platform(),
                "runs": len(elapsed),
                "model_calls": 0,
                "p50_ms": round(percentile(elapsed, 0.5), 2),
                "p95_ms": round(percentile(elapsed, 0.95), 2),
                "samples_ms": [round(item, 2) for item in elapsed],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
