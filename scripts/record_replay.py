"""Export schema-valid local decisions for the bundled demonstration."""

import argparse
import json
from pathlib import Path

from trl.scenarios import load_scenario
from trl.storage import RunStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    parser.add_argument("run_id")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    store = RunStore(args.database)
    run = store.read(args.run_id)
    scenario = load_scenario()
    if (
        run.scenario != scenario
        or run.notice != scenario.notice
        or run.status != "verified"
    ):
        raise SystemExit(
            "Export requires the verified bundled demonstration with its original notice."
        )
    calls = store.calls(run.id, run.version)
    frames = {
        call.request_sha256: json.loads(call.content)
        for call in calls
        if call.state == "valid" and call.content and call.request_sha256
    }
    if not frames or any(call.model == "replay" for call in calls):
        raise SystemExit("Run the demonstration with a real local model first.")
    args.output.write_text(
        json.dumps(
            {
                "kind": "recorded_replay",
                "notice": scenario.notice,
                "operator": json.loads(
                    next(call.content for call in calls if call.content)
                ),
                "models": sorted({call.digest for call in calls}),
                "recorded": frames,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
