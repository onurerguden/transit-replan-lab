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
    parser.add_argument("--runs", type=int, default=30)
    options = parser.parse_args()
    if options.runs < 2:
        parser.error("--runs must include a first run and at least one warm run.")
    elapsed: list[float] = []
    notice = load_scenario().notice
    startup = perf_counter()
    with (
        TemporaryDirectory() as workspace,
        TestClient(create_app(Path(workspace) / "profile.sqlite")) as client,
    ):
        startup_ms = (perf_counter() - startup) * 1000
        for number in range(options.runs):
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
    with options.output.open("x", encoding="utf-8") as handle:
        json.dump(
            {
                "source_digest": code_digest(),
                "system": platform.platform(),
                "runs": len(elapsed),
                "model_calls": 0,
                "app_startup_ms": round(startup_ms, 2),
                "first_command_ms": round(elapsed[0], 2),
                "warm_p50_ms": round(percentile(elapsed[1:], 0.5), 2),
                "warm_p95_ms": round(percentile(elapsed[1:], 0.95), 2),
                "p50_ms": round(percentile(elapsed, 0.5), 2),
                "p95_ms": round(percentile(elapsed, 0.95), 2),
                "samples_ms": [round(item, 2) for item in elapsed],
            },
            handle,
            indent=2,
        )
        handle.write("\n")


if __name__ == "__main__":
    main()
