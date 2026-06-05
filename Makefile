VENV_BIN := .venv/bin
PYTEST := $(if $(wildcard $(VENV_BIN)/pytest),$(VENV_BIN)/pytest,pytest)
RUFF := $(if $(wildcard $(VENV_BIN)/ruff),$(VENV_BIN)/ruff,ruff)
ALEMBIC := $(if $(wildcard $(VENV_BIN)/alembic),../../$(VENV_BIN)/alembic,alembic)
UVICORN := $(if $(wildcard $(VENV_BIN)/uvicorn),../../$(VENV_BIN)/uvicorn,uvicorn)
NODE20_BIN := /opt/homebrew/opt/node@20/bin
WEB_PATH := $(if $(wildcard $(NODE20_BIN)/node),$(NODE20_BIN):$(PATH),$(PATH))

.PHONY: dev up down migrate seed process-demo doctor test lint format reset-data verify release-check

dev:
	@printf "Start API and web separately for local hacking:\n"
	@printf "  cd apps/api && $(UVICORN) app.main:app --reload\n"
	@printf "  cd apps/web && PATH=\"$(WEB_PATH)\" npm run dev\n"

up:
	docker compose up --build

down:
	docker compose down

migrate:
	cd apps/api && $(ALEMBIC) upgrade head

seed process-demo:
	curl -X POST http://localhost:8000/api/process/demo

doctor:
	python3 scripts/doctor.py

test:
	$(PYTEST) apps/api/tests
	cd apps/web && PATH="$(WEB_PATH)" npm test

lint:
	$(RUFF) check apps/api/app apps/api/tests scripts
	cd apps/web && PATH="$(WEB_PATH)" npm run lint

verify: test lint
	cd apps/web && PATH="$(WEB_PATH)" npm run build

release-check: verify
	python3 scripts/release_check.py --require-clean

format:
	$(RUFF) format apps/api/app apps/api/tests scripts
	cd apps/web && PATH="$(WEB_PATH)" npm run format

reset-data:
	curl -X POST -H "X-Demo-Reset-Token: $$DEMO_RESET_TOKEN" http://localhost:8000/api/process/demo?reset=true
