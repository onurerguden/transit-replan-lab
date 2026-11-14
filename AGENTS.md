# AGENTS.md

## Mission

Build a local, timetable-backed simulator that coordinates two riders after a transit disruption in İzmir. v1 covered Metro M1 and Konak Tram, four coordination variants, independent route verification, local inference, an Operator adaptation experiment, and a reproducible release. v2 extends the network to all five official İzmir GTFS feeds and keeps Metro M1 and Konak Tram as the `core` demo profile. Live transit data, hosted deployments, steps that need external accounts or API keys, rider accounts, and travel advice remain out of scope. The [v2 plan](docs/v2/engineering-plan.md) and the [roadmap](docs/roadmap.md) track the work.

## System invariants

- Routing and verification are deterministic. The verifier uses the domain and GTFS loader directly and never imports routing.
- A verified offer requires two distinct current-version rider acceptances for that offer and a passing independent verification.
- Application writes are version-checked and idempotent by step key. Run model calls outside SQLite transactions. A checkpoint tracks execution position. Application tables own the outcome.
- Models cannot change hard rider constraints. Accept constraint changes only through an explicit user input.
- Freeze the locked sets before evaluation. During development use the development partitions. Generate experiment outputs from the runner.
- Label inferred transfer properties and simulated incident data as assumptions.

## Publication boundary

Keep unrelated private material, personal data, and credentials outside the repository, including fixtures, prompts, training data, and Git messages. Use an ignored local denylist and the staged and history checks. Inspect generated artifacts before publication.

## Workspace and checks

- `backend/` contains the Python service and tests. `frontend/` contains the React application.
- `data/` holds sources and scenarios. `experiments/` and `finetune/` hold evaluation and training tooling as those phases land.
- `docs/` contains architecture, decisions, and the [phase checklist](docs/roadmap.md).
- Run `make setup`, `make check`, `make test`, `make build`, and `make hooks` from the root. Run `make dev-api` and `make dev-web` in separate terminals.
- `make test-ollama` runs real-model tests, `make test-deep` runs the nightly property and differential suites, `make api-drift` checks the OpenAPI schema and generated client, and `make e2e` runs the browser suite. The roadmap tracks the v2 benchmark, load and training targets.
- `trl.settings` is the only place that reads environment variables.

## Change discipline

Complete the active phase checklist and keep its docs current. Verify relevant behavior with tests, run the checks, and use Conventional Commits. Explain architectural changes in an ADR and bump the version of changed prompts. Obtain the maintainer's approval for phase commits and publication.
