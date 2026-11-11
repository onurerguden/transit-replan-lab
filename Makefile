SHELL := /bin/sh
PY := uv run --locked --project backend
WEB := cd frontend && corepack pnpm

.PHONY: setup check test build dev dev-api dev-web hooks verify-public

setup:
	uv sync --locked --project backend
	$(WEB) install --frozen-lockfile

check:
	$(PY) ruff check backend scripts
	$(PY) ruff format --check backend scripts
	$(PY) pyright --project backend/pyproject.toml
	$(PY) pytest backend/tests -m "not ollama"
	cd backend && uv run --locked lint-imports
	$(WEB) run lint
	$(WEB) run typecheck
	$(WEB) run test
	$(PY) python scripts/check_public_boundary.py

test:
	$(PY) pytest backend/tests
	$(WEB) run test

build:
	$(WEB) run build

dev: dev-api

dev-api:
	$(PY) uvicorn trl.api.app:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend/src

dev-web:
	$(WEB) run dev

hooks:
	$(PY) pre-commit install --hook-type pre-commit --hook-type commit-msg

verify-public:
	$(PY) python scripts/check_public_boundary.py --staged --history --require-denylist
