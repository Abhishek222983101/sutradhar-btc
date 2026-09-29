# Sutradhar — developer commands. `make` lists them.
SHELL := /bin/bash
.DEFAULT_GOAL := help
PY := uv run
GITLEAKS := docker run --rm -v "$(CURDIR)":/repo:ro ghcr.io/gitleaks/gitleaks:latest

.PHONY: help setup lint fmt typecheck test test-all security security-deps check

help: ## List every target
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Install Python (uv) and web (pnpm) dependencies
	uv sync
	@if [ -f package.json ]; then pnpm install; fi

lint: ## Lint, format check and module-boundary contracts (I18)
	$(PY) ruff check .
	$(PY) ruff format --check .
	$(PY) lint-imports

fmt: ## Auto-format and auto-fix
	$(PY) ruff format .
	$(PY) ruff check --fix .

typecheck: ## Static types (pyright) and TypeScript
	@if [ -f package.json ]; then pnpm -s typecheck; fi

test: ## Fast tests (excludes @slow)
	$(PY) pytest -q -m "not slow"

test-all: ## Every test, including slow ones
	$(PY) pytest -q

security: ## Security gate: SAST + dependency audit + secret scan + security tests
	$(PY) ruff check --select S .
	$(PY) bandit -q -r packages apps/api -c pyproject.toml
	$(PY) pip-audit --skip-editable --progress-spinner off
	@if [ -d .git ] && git rev-parse HEAD >/dev/null 2>&1; then $(GITLEAKS) git /repo --redact --no-banner; else $(GITLEAKS) dir /repo --redact --no-banner --max-target-megabytes 5; fi
	$(PY) pytest -q -m security
	@if [ -d apps/web/node_modules ]; then pnpm audit --prod; fi

check: lint test security ## Everything a sub-phase must pass before it is done
