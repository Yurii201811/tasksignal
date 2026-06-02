.PHONY: dev up down migrate seed process-demo doctor test lint format reset-data verify release-check

dev:
	@printf "Start API and web separately for local hacking:\n"
	@printf "  cd apps/api && uvicorn app.main:app --reload\n"
	@printf "  cd apps/web && npm run dev\n"

up:
	docker compose up --build

down:
	docker compose down

migrate:
	cd apps/api && alembic upgrade head

seed process-demo:
	curl -X POST http://localhost:8000/api/process/demo

doctor:
	python3 scripts/doctor.py

test:
	cd apps/api && pytest
	cd apps/web && npm test

lint:
	cd apps/api && ruff check app tests
	cd apps/web && npm run lint

verify: test lint
	cd apps/web && npm run build

release-check: verify
	python3 scripts/release_check.py --require-clean

format:
	cd apps/api && ruff format app tests
	cd apps/web && npm run format

reset-data:
	curl -X POST -H "X-Demo-Reset-Token: $$DEMO_RESET_TOKEN" http://localhost:8000/api/process/demo?reset=true
