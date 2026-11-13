# v2 implementation log

Each entry records completed acceptance checks and concrete blockers.

## F0 · Baseline and guardrails

- Work happens on `feat/v2-engineering` in the existing review worktree, created from
  `origin/main` (`1dfe799`). A separate worktree was unnecessary because the review branch was
  already merged and its tree matches the baseline.
- [Baseline](baseline.md) recorded: 74 deterministic tests, 87% branch coverage across `trl`,
  demo search p50 386 ms.
- [`test_v2_defects.py`](../../backend/tests/test_v2_defects.py) records 27 reproduced defect
  cases as strict expected failures and one guard that passes.
- `trl.settings` validates every environment variable. The API is created by a factory
  (`uvicorn --factory trl.api.app:create_app`). The database default no longer depends on the
  working directory.
- One version source: `2.0.0.dev0` in the package metadata, the API schema and the frontend
  package, checked by `test_versions_have_one_source`.
- Lint now covers complexity, blind excepts, async blocking, security and pytest style.
  Exceptions are listed per file with the phase that removes them. Production asserts became
  explicit errors.
- Branch coverage spans all of `trl` with a floor of 86%, ratcheting to 90%.
- `make test` is hermetic. `make test-ollama`, `make test-deep` and `make api-drift` are new.
- CI is split into backend (Ubuntu and macOS), frontend, browser and Docker, and a nightly deep
  job. Actions are pinned by commit SHA, caches are enabled, and browser traces upload on failure.
  Dependabot covers actions, uv and npm.
