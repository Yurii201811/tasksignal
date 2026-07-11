API_VENV_BIN := apps/api/.venv/bin
API_PYTHON := $(API_VENV_BIN)/python
RUFF := $(API_VENV_BIN)/ruff
NODE20_BIN := /opt/homebrew/opt/node@20/bin
WEB_PATH := $(if $(wildcard $(NODE20_BIN)/node),$(NODE20_BIN):$(PATH),$(PATH))
PIP_AUDIT_VERSION := 2.10.1
TWINE_VERSION := 6.2.0

.PHONY: setup setup-ml dev up down migrate migrate-native seed process-demo doctor smoke test lint format reset-data verify npm-audit python-audit package-check release-proof release-check

setup:
	uv sync --project apps/api --extra dev --locked
	PATH="$(WEB_PATH)" npm --prefix apps/web ci

setup-ml:
	uv sync --project apps/api --extra dev --extra ml --locked
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

NPM_AUDIT := cd apps/web && PATH="$(WEB_PATH)" npm audit --audit-level=moderate

npm-audit:
	$(NPM_AUDIT)

python-audit:
	@requirements="$$(mktemp /tmp/tasksignal-audit.XXXXXX.txt)"; \
	trap 'rm -f "$$requirements"' EXIT; \
	uv export --quiet --project apps/api --locked --no-dev --extra mcp \
		--no-emit-project --no-header --no-annotate \
		--output-file "$$requirements"; \
	uvx --from pip-audit==$(PIP_AUDIT_VERSION) pip-audit \
		--requirement "$$requirements" --progress-spinner off --strict \
		--require-hashes --disable-pip

package-check:
	@dist_dir="$$(mktemp -d /tmp/tasksignal-dist.XXXXXX)"; \
	trap 'rm -rf "$$dist_dir"' EXIT; \
	uv build --project apps/api --out-dir "$$dist_dir"; \
	uvx --from twine==$(TWINE_VERSION) twine check "$$dist_dir"/*; \
	wheel="$$(find "$$dist_dir" -maxdepth 1 -type f -name '*.whl')"; \
	test "$$(printf '%s\n' "$$wheel" | sed '/^$$/d' | wc -l | tr -d ' ')" = 1; \
	python3 scripts/smoke_built_wheel.py --wheel "$$wheel"

release-proof:
	@proof_dir="$$(mktemp -d /tmp/tasksignal-proof.XXXXXX)"; \
	trap 'rm -rf "$$proof_dir"' EXIT; \
	$(API_PYTHON) -u scripts/first_run_smoke.py --proof-dir "$$proof_dir"; \
	$(API_PYTHON) -u scripts/first_run_smoke.py --verify-proof-dir "$$proof_dir"

release-check: verify
	$(MAKE) npm-audit
	$(MAKE) python-audit
	$(MAKE) package-check
	$(MAKE) release-proof
	$(API_PYTHON) scripts/release_check.py --require-clean

format:
	$(RUFF) format apps/api/app apps/api/tests scripts
	cd apps/web && PATH="$(WEB_PATH)" npm run format

reset-data:
	curl -X POST -H "X-Demo-Reset-Token: $$DEMO_RESET_TOKEN" http://localhost:8000/api/process/demo?reset=true
