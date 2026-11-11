SHELL := /bin/sh
PY := uv run --locked --project backend
WEB := cd frontend && corepack pnpm

.PHONY: setup check test build e2e dev dev-api dev-web hooks verify-public

setup:
	uv sync --locked --project backend
	$(WEB) install --frozen-lockfile

check:
	$(PY) ruff check backend scripts experiments finetune
	$(PY) ruff format --check backend scripts experiments finetune
	$(PY) pyright --project backend/pyproject.toml
	$(PY) pytest backend/tests -m "not ollama" \
		--cov=trl.routing --cov=trl.verify --cov=trl.disruptions --cov=trl.storage \
		--cov-report=term-missing --cov-fail-under=90
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
