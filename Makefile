SHELL := /bin/sh
# Branch coverage across trl. Ratchets to 90 by the v2 release.
COVERAGE_FLOOR ?= 88
PY := uv run --locked --project backend
WEB := cd frontend && corepack pnpm

.PHONY: setup check test test-ollama test-deep api-types api-drift build e2e dev dev-api dev-web hooks verify-public

setup:
	uv sync --locked --project backend
	$(WEB) install --frozen-lockfile

check:
	$(PY) ruff check backend scripts experiments finetune
	$(PY) ruff format --check backend scripts experiments finetune
	$(PY) pyright --project backend/pyproject.toml
	$(PY) pytest backend/tests -m "not ollama and not deep" \
		--cov --cov-config=backend/pyproject.toml --cov-report=term --cov-fail-under=$(COVERAGE_FLOOR)
	cd backend && uv run --locked lint-imports
	$(WEB) run lint
	$(WEB) run typecheck
	$(WEB) run test
	$(PY) python scripts/check_public_boundary.py

test:
	$(PY) pytest backend/tests -m "not ollama and not deep"
	$(WEB) run test

# Real-model tests need a running Ollama instance with the pinned tag.
test-ollama:
	$(PY) pytest backend/tests -m ollama

# Long property, differential and state-machine suites. CI runs them nightly.
test-deep:
	TRL_DEEP=1 $(PY) pytest backend/tests -m deep

api-types:
	$(PY) python scripts/export_openapi.py
	$(WEB) run api:types

# Fail when the checked schema or generated client types drift from the backend.
api-drift: api-types
	git diff --exit-code -- frontend/openapi.json frontend/src/api.generated.ts

build:
	$(WEB) run build

dev:
	$(MAKE) -j2 dev-api dev-web

dev-api:
	$(PY) uvicorn --factory trl.api.app:create_app --host 127.0.0.1 --port 8000 --reload --reload-dir backend/src

dev-web:
	$(WEB) run dev

hooks:
	$(PY) pre-commit install --hook-type pre-commit --hook-type commit-msg

verify-public:
	$(PY) python scripts/check_public_boundary.py --staged --history --require-denylist

e2e:
	$(WEB) run e2e

.PHONY: experiment
experiment:
	$(PY) python -m experiments.runner $(EXPERIMENT_ARGS)

FT_PY ?= .local/mlx/venv/bin/python
FT_MODEL ?= .local/mlx/qwen35-4b
FINETUNE_SPLIT ?= valid

.PHONY: finetune-data finetune-pilot finetune finetune-eval
finetune-data:
	$(PY) python -m finetune.data
	cmp finetune/manifest.json .local/finetune/data/manifest.json
	mkdir -p .local/finetune/training
	cp .local/finetune/data/train.jsonl .local/finetune/data/valid.jsonl .local/finetune/training/
	test ! -e .local/finetune/training/test.jsonl

finetune-pilot: finetune-data
	$(FT_PY) -m mlx_lm lora --config finetune/pilot.yml --model "$(FT_MODEL)"

finetune: finetune-data
	$(FT_PY) -m mlx_lm lora --config finetune/train.yml --model "$(FT_MODEL)"

finetune-eval:
	$(FT_PY) -m finetune.evaluate --model "$(FT_MODEL)" --split "$(FINETUNE_SPLIT)" \
		--output ".local/finetune/$(FINETUNE_SPLIT).json"
