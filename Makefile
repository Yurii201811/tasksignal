API_VENV_BIN := apps/api/.venv/bin
API_PYTHON := $(API_VENV_BIN)/python
RUFF := $(API_VENV_BIN)/ruff
NODE20_BIN := /opt/homebrew/opt/node@20/bin
WEB_PATH := $(if $(wildcard $(NODE20_BIN)/node),$(NODE20_BIN):$(PATH),$(PATH))

.PHONY: setup dev up down migrate migrate-native seed process-demo doctor smoke test lint format reset-data verify release-check

setup:
	uv sync --project apps/api --extra dev --locked
	PATH="$(WEB_PATH)" npm --prefix apps/web ci

dev:
	@printf "Start API and web separately for local hacking:\n"
	@printf "  cd apps/api && .venv/bin/uvicorn app.main:app --reload\n"
	@printf "  cd apps/web && PATH=\"$(WEB_PATH)\" npm run dev\n"

up:
	docker compose up --build

down:
	docker compose down

migrate:
	docker compose run --rm --build api alembic upgrade head

migrate-native:
	cd apps/api && .venv/bin/alembic upgrade head

seed process-demo:
	curl -X POST http://localhost:8000/api/process/demo

doctor:
	python3 scripts/doctor.py

smoke:
	$(API_PYTHON) -u scripts/first_run_smoke.py

test:
	$(API_PYTHON) -m pytest apps/api/tests
	cd apps/web && PATH="$(WEB_PATH)" npm test

lint:
	$(API_PYTHON) scripts/check_fixture_redaction.py
	$(RUFF) check apps/api/app apps/api/tests scripts
	cd apps/web && PATH="$(WEB_PATH)" npm run lint

verify: test lint
	cd apps/web && PATH="$(WEB_PATH)" npm run build

release-check: verify
	$(API_PYTHON) scripts/release_check.py --require-clean

format:
	$(RUFF) format apps/api/app apps/api/tests scripts
	cd apps/web && PATH="$(WEB_PATH)" npm run format

reset-data:
	curl -X POST -H "X-Demo-Reset-Token: $$DEMO_RESET_TOKEN" http://localhost:8000/api/process/demo?reset=true
