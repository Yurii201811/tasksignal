# TaskSignal v0.2 Decision Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship TaskSignal development version 0.2.0 as a local-first decision workbench with persisted opportunity decisions, append-only evidence reviews, transparent evidence readiness, honest evaluation metrics, decision-aware exports, and a fully verified browser workflow.

**Architecture:** Keep opportunity decision persistence in the existing model, put latest-label/readiness/evaluation calculations in a focused backend review service, expose typed FastAPI contracts, and render backend-owned results through focused React components. Preserve the single-operator fixture path, bind default runtime ports to loopback, and omit local review notes from shared exports.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, SQLite/PostgreSQL, pytest, ruff, Next.js 15, React 19, TypeScript, TanStack Query, Tailwind CSS, Vitest, Testing Library, Docker Compose, Node 20.

## Global Constraints

- Preserve the local-first, single-operator posture and credential-free fixture workflow.
- Use only these opportunity states: `new`, `needs_more_evidence`, `promising`, `rejected`, `duplicate`, `build_candidate`.
- Use only these new evidence labels: `true_signal`, `false_positive`, `unclear`, `duplicate`, `not_actionable`, `sensitive_risk`.
- Opportunity review notes are at most 1,000 characters; evidence review notes are at most 500 characters.
- Evidence readiness means review readiness, never confidence, market validation, adoption, or demand.
- Report precision only as `true_signal / (true_signal + false_positive)` on manually reviewed evidence; do not report recall or F1.
- Keep evidence labels append-only and select the latest stored row by `created_at DESC, id DESC`; an unrecognized latest row yields no current recognized label.
- Do not include opportunity or evidence review notes in task-pack or evidence exports.
- Do not repurpose `OPERATOR_SCAN_TOKEN` as authentication; bind default host ports to `127.0.0.1` and document that public/team deployments require authentication and workspace isolation.
- Use `apps/api/.venv` for API tooling, Homebrew Node 20 when present, and no frontend framework major-version upgrade.
- Keep the actual published-release link at v0.1.3; change only development metadata to `0.2.0`.
- Do not push, tag, publish a GitHub release, update tickets, or mutate a deployed environment.
- Never stage or modify the pre-existing `.oss-steward/` directory or `docs/audits/v0.2-issue-roadmap-2026-06-20.md`.

---

## File Structure

### Backend domain and persistence

- `apps/api/app/models/all_models.py`: persisted opportunity decision fields.
- `apps/api/alembic/versions/0006_decision_workbench.py`: upgrade/downgrade for decision columns and index.
- `apps/api/app/db/session.py`: additive compatibility repair for existing SQLite databases.
- `apps/api/app/services/evidence_review/types.py`: shared string enums and review snapshot dataclass.
- `apps/api/app/schemas/api.py`: review/evaluation/readiness request and response contracts.
- `apps/api/app/services/evidence_review/service.py`: latest-label selection, evidence readiness, and aggregate evaluation.
- `apps/api/app/api/routes.py`: serialization, review/label/evaluation endpoints, filters, and decision-aware exports.

### Backend tests and proof

- `apps/api/tests/test_decision_workbench.py`: domain and API behavior for decisions, evidence reviews, readiness, evaluation, and exports.
- `apps/api/tests/test_sqlite_schema_compatibility.py`: stale SQLite repair and preserved defaults/indexes.
- `apps/api/tests/test_api.py`: existing response/export regressions and unsafe-URL fixtures.
- `apps/api/tests/test_first_run_smoke.py`: proof-summary and decision-workflow assertions.
- `scripts/first_run_smoke.py`: credential-free end-to-end decision/evaluation/export proof.

### Frontend domain and surfaces

- `apps/web/src/lib/types.ts`: exact API types.
- `apps/web/src/lib/review.ts`: ordered state/label/check metadata and display helpers.
- `apps/web/src/lib/api-error.ts`: one backend/Pydantic error formatter.
- `apps/web/src/lib/api.ts`: review, label history, evaluation, and optional state-filter calls.
- `apps/web/src/components/ui.tsx`: shared `Textarea` primitive.
- `apps/web/src/features/opportunity-decision-panel.tsx`: persisted decision form.
- `apps/web/src/features/evidence-readiness-card.tsx`: backend-owned readiness presentation.
- `apps/web/src/features/evidence-review-control.tsx`: append-only evidence review form.
- `apps/web/src/features/opportunity-detail.tsx`: integrates the three focused review components.
- `apps/web/src/features/dashboard.tsx`: local decision counts/filter and state/readiness columns.
- `apps/web/src/features/evaluation.tsx`: aggregate evaluation page content.
- `apps/web/src/app/evaluation/page.tsx`: Evaluation route.
- `apps/web/src/components/app-shell.tsx`: Evaluation navigation.

### Frontend tests

- `apps/web/tests/api.test.ts`: exact HTTP methods, paths, encoding, and payloads.
- `apps/web/tests/opportunity-decision-panel.test.tsx`: persisted decision behavior.
- `apps/web/tests/evidence-readiness-card.test.tsx`: readiness language/check rendering.
- `apps/web/tests/evidence-review-control.test.tsx`: append-only review behavior.
- `apps/web/tests/dashboard.test.tsx`: counts, filtering, state/readiness table.
- `apps/web/tests/evaluation.test.tsx`: metrics, breakdowns, and empty/error states.
- `apps/web/tests/opportunity-detail.test.tsx`: integration and existing enhancement regression.
- `apps/web/tests/app-shell.test.tsx`: Evaluation navigation state.

### Setup, security, version, and documentation

- `Makefile`, `scripts/doctor.py`, `apps/api/tests/test_doctor.py`, `CONTRIBUTING.md`: reproducible locked `make setup` and one API virtualenv path.
- `docker-compose.yml`, `apps/web/package.json`, `apps/web/package-lock.json`: loopback defaults, Node workflow, dependency remediation, web version.
- `apps/api/pyproject.toml`, `apps/api/uv.lock`, `apps/api/app/main.py`, `CHANGELOG.md`: development version 0.2.0.
- `README.md`, `docs/api.md`, `docs/model-card.md`, `docs/roadmap.md`, `docs/demo-evidence.md`, `docs/architecture.md`, `docs/deployment.md`, `docs/threat-model.md`: behavior, limits, setup, and security truth.

---

### Task 1: Standardize the local development toolchain

**Files:**
- Create: `apps/api/tests/test_doctor.py`
- Modify: `Makefile:1-53`
- Modify: `scripts/doctor.py:13-15,120-141`
- Modify: `CONTRIBUTING.md:5-43`

**Interfaces:**
- Consumes: existing API project at `apps/api/pyproject.toml` and web lockfile at `apps/web/package-lock.json`.
- Produces: `make setup`, `API_VENV_BIN := apps/api/.venv/bin`, and doctor output that consistently points to `apps/api/.venv/bin`.

- [ ] **Step 1: Write the failing doctor path test**

Create `apps/api/tests/test_doctor.py`:

```python
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("tasksignal_doctor", ROOT / "scripts/doctor.py")
assert SPEC and SPEC.loader
doctor = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = doctor
SPEC.loader.exec_module(doctor)


def test_doctor_uses_api_project_virtualenv() -> None:
    assert doctor.VENV_BIN == ROOT / "apps" / "api" / ".venv" / "bin"


def test_missing_tool_guidance_names_api_project_virtualenv(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda _path: False)
    monkeypatch.setattr(doctor.shutil, "which", lambda _command: None)

    check = doctor.check_python_tool("pytest", "pytest")

    assert check.status == "fail"
    assert "apps/api/.venv/bin/pytest" in check.detail


def test_missing_frontend_dependencies_point_to_setup(monkeypatch) -> None:
    monkeypatch.setattr(Path, "exists", lambda _path: False)

    check = doctor.check_frontend_dependencies()

    assert check.status == "fail"
    assert "make setup" in check.detail
```

- [ ] **Step 2: Run the focused test and confirm the old root-venv contract fails**

Run:

```bash
uv run --project apps/api --extra dev --locked \
  pytest -p no:cacheprovider apps/api/tests/test_doctor.py -v
```

Expected: FAIL because `VENV_BIN` currently resolves to `<repo>/.venv/bin` and the message names `.venv/bin/pytest`.

- [ ] **Step 3: Implement the single toolchain path and setup target**

In `scripts/doctor.py`, replace the virtualenv constant and missing-tool strings with:

```python
VENV_BIN = ROOT / "apps" / "api" / ".venv" / "bin"
WEB_NEXT_BIN = ROOT / "apps" / "web" / "node_modules" / ".bin" / "next"


def check_python_tool(command: str, package_hint: str) -> Check:
    executable = VENV_BIN / command
    relative_executable = executable.relative_to(ROOT)
    if executable.exists():
        version = run([executable, "--version"]) or "found"
        return Check(command, "ok", f"{version} via {relative_executable}")

    fallback = shutil.which(command)
    if fallback:
        version = run([fallback, "--version"]) or "found"
        return Check(command, "warn", f"{version} on PATH; prefer {relative_executable}")

    return Check(
        command,
        "fail",
        f"missing; run make setup so {relative_executable} exists ({package_hint})",
    )


def check_frontend_dependencies() -> Check:
    if WEB_NEXT_BIN.exists():
        return Check(
            "frontend dependencies",
            "ok",
            "apps/web/node_modules/.bin/next is present",
        )
    return Check(
        "frontend dependencies",
        "fail",
        "missing; run make setup so apps/web/node_modules is installed",
    )
```

Add `"apps/api/uv.lock"` to `REQUIRED_PATHS`, include `uv` in the runtime loop,
add `check_python_tool("alembic", "alembic")`, and append
`check_frontend_dependencies()` in `main()`:

```python
def check_runtime_commands() -> list[Check]:
    checks: list[Check] = []
    for command in ["python3", "uv", "node", "npm"]:
        executable = command_path(command)
        if executable is None:
            checks.append(
                Check(command, "fail", "not found; install it before running TaskSignal")
            )
            continue

        version = run([executable, "--version"])
        if command == "node" and version:
            major = version_major(version)
            if major is not None and major < MIN_NODE_MAJOR:
                checks.append(
                    Check(
                        command,
                        "fail",
                        f"{version}; use Node {MIN_NODE_MAJOR}+ for the Next.js web app",
                    )
                )
                continue

        source = f" via {executable}" if Path(str(executable)).is_absolute() else ""
        checks.append(Check(command, "ok", f"{version or 'found'}{source}"))

    docker = shutil.which("docker")
    if docker is None:
        checks.append(
            Check("docker", "warn", "not found; Docker Compose quickstart will not work")
        )
    else:
        checks.append(Check("docker", "ok", run([docker, "--version"]) or "found"))
    return checks


def main() -> int:
    checks = [
        *check_required_paths(),
        check_env_file(),
        *check_runtime_commands(),
        check_python_tool("pytest", "pytest"),
        check_python_tool("ruff", "ruff"),
        check_python_tool("uvicorn", "uvicorn[standard]"),
        check_python_tool("alembic", "alembic"),
        check_frontend_dependencies(),
        check_git_generated_files(),
        check_fixture_count(),
    ]
    print_checks(checks)

    failures = [check for check in checks if check.status == "fail"]
    warnings = [check for check in checks if check.status == "warn"]
    if failures:
        print(f"\nDoctor failed: {len(failures)} blocker(s), {len(warnings)} warning(s).")
        return 1

    print(f"\nDoctor passed: no blockers, {len(warnings)} warning(s).")
    return 0
```

Replace the Makefile variable/affected-target block with:

```make
API_VENV_BIN := apps/api/.venv/bin
API_PYTHON := $(API_VENV_BIN)/python
RUFF := $(API_VENV_BIN)/ruff
NODE20_BIN := /opt/homebrew/opt/node@20/bin
WEB_PATH := $(if $(wildcard $(NODE20_BIN)/node),$(NODE20_BIN):$(PATH),$(PATH))

.PHONY: setup dev up down migrate seed process-demo doctor smoke test lint format reset-data verify release-check

setup:
	uv sync --project apps/api --extra dev --locked
	PATH="$(WEB_PATH)" npm --prefix apps/web ci

dev:
	@printf "Start API and web separately for local hacking:\n"
	@printf "  cd apps/api && .venv/bin/uvicorn app.main:app --reload\n"
	@printf "  cd apps/web && PATH=\"$(WEB_PATH)\" npm run dev\n"

migrate:
	cd apps/api && .venv/bin/alembic upgrade head

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
```

Keep the existing `up`, `down`, `seed process-demo`, and `reset-data` recipes unchanged.

Replace the development setup section in `CONTRIBUTING.md` with:

````markdown
## Development Setup

1. Install the locked API and web development dependencies:

   ```bash
   make setup
   ```

2. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

3. Run the local setup diagnostic:

   ```bash
   make doctor
   ```

4. Start the API and web app in separate terminals:

   ```bash
   cd apps/api
   .venv/bin/uvicorn app.main:app --reload
   ```

   ```bash
   cd apps/web
   npm run dev
   ```

Use `make up` instead when you want the full Docker Compose stack.
````

- [ ] **Step 4: Install locked dependencies and verify the toolchain**

Run:

```bash
make setup
make doctor
apps/api/.venv/bin/python -m pytest apps/api/tests/test_doctor.py -v
```

Expected: `make setup` exits 0, doctor reports `pytest`, `ruff`, and `uvicorn`
from `apps/api/.venv/bin`, and all three doctor tests pass.

- [ ] **Step 5: Commit the toolchain checkpoint**

```bash
git add Makefile scripts/doctor.py apps/api/tests/test_doctor.py CONTRIBUTING.md
git commit -m "build: standardize TaskSignal local setup"
```

---

### Task 2: Persist opportunity decisions and repair stale SQLite databases

**Files:**
- Create: `apps/api/alembic/versions/0006_decision_workbench.py`
- Create: `apps/api/app/services/evidence_review/types.py`
- Modify: `apps/api/app/models/all_models.py:202-219`
- Modify: `apps/api/app/db/session.py:12-48`
- Modify: `apps/api/app/schemas/api.py:1-5,158-178,193-196`
- Modify: `apps/api/tests/test_sqlite_schema_compatibility.py:1-43`
- Modify: `apps/api/tests/test_api.py:34-49`

**Interfaces:**
- Consumes: `Opportunity`, `now_utc`, `ensure_sqlite_schema_compatibility`, and `OpportunityOut`.
- Produces: shared `ReviewState`, `EvidenceReviewLabel`, `EvidenceReadinessLevel`, `EvidenceReviewSnapshot`, `OpportunityReviewUpdate`, persisted `review_state`, `review_note`, `decision_updated_at`, and SQLite index `ix_opportunities_review_state`.

- [ ] **Step 1: Write failing persistence and SQLite compatibility tests**

Append to `test_process_demo_endpoint` in `apps/api/tests/test_api.py`:

```python
    assert opportunities[0]["review_state"] == "new"
    assert opportunities[0]["review_note"] is None
    assert opportunities[0]["decision_updated_at"] is None
```

Extend `test_sqlite_schema_compatibility_adds_missing_local_columns` with an old opportunity row and exact assertions:

```python
        connection.execute(text("CREATE TABLE opportunities (id TEXT PRIMARY KEY)"))
        connection.execute(text("INSERT INTO opportunities (id) VALUES ('opportunity-1')"))

    # after ensure_sqlite_schema_compatibility(engine)
    opportunity_columns = {
        column["name"] for column in inspector.get_columns("opportunities")
    }
    assert {"review_state", "review_note", "decision_updated_at"}.issubset(
        opportunity_columns
    )
    opportunity_indexes = {
        index["name"] for index in inspector.get_indexes("opportunities")
    }
    assert "ix_opportunities_review_state" in opportunity_indexes

    with engine.connect() as connection:
        opportunity_row = connection.execute(
            text(
                "SELECT review_state, review_note, decision_updated_at "
                "FROM opportunities WHERE id = 'opportunity-1'"
            )
        ).one()
    assert opportunity_row == ("new", None, None)
```

Add `os`, `subprocess`, `sys`, and `Path` imports to that test module, then add
this migration data-preservation test:

```python
ROOT = Path(__file__).resolve().parents[3]
API_DIR = ROOT / "apps" / "api"


def run_alembic(database_url: str, *args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": database_url},
        check=True,
    )


def test_decision_migration_preserves_existing_opportunity(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    run_alembic(database_url, "upgrade", "0005_scan_outcomes")
    migration_engine = create_engine(database_url)
    now = "2026-07-09T12:00:00+00:00"
    cluster_id = "11111111111111111111111111111111"
    opportunity_id = "22222222222222222222222222222222"
    with migration_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO clusters "
                "(id, title, summary, centroid_embedding, size, created_at, updated_at) "
                "VALUES (:id, :title, :summary, NULL, 1, :created_at, :updated_at)"
            ),
            {
                "id": cluster_id,
                "title": "Existing cluster",
                "summary": "Existing summary",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text(
                "INSERT INTO opportunities "
                "(id, cluster_id, title, problem_statement, target_user, "
                "current_workaround, suggested_mvp, why_now, feasibility_score, "
                "opportunity_score, competition_notes, scoring_breakdown_json, "
                "generated_prompt, created_at, updated_at) VALUES "
                "(:id, :cluster_id, :title, :problem, :target, :workaround, :mvp, "
                ":why_now, 0.8, 0.7, :competition, :breakdown, :prompt, "
                ":created_at, :updated_at)"
            ),
            {
                "id": opportunity_id,
                "cluster_id": cluster_id,
                "title": "Existing decision candidate",
                "problem": "Existing problem",
                "target": "Maintainers",
                "workaround": "Manual review",
                "mvp": "Decision queue",
                "why_now": "Evidence exists",
                "competition": "Narrow scope",
                "breakdown": "{}",
                "prompt": "# Build existing candidate",
                "created_at": now,
                "updated_at": now,
            },
        )
    migration_engine.dispose()

    run_alembic(database_url, "upgrade", "head")
    upgraded_engine = create_engine(database_url)
    with upgraded_engine.connect() as connection:
        upgraded = connection.execute(
            text(
                "SELECT review_state, review_note, decision_updated_at, title "
                "FROM opportunities WHERE id = :id"
            ),
            {"id": opportunity_id},
        ).one()
    assert upgraded == ("new", None, None, "Existing decision candidate")
    upgraded_engine.dispose()

    run_alembic(database_url, "downgrade", "0005_scan_outcomes")
    downgraded_engine = create_engine(database_url)
    columns = {
        column["name"] for column in inspect(downgraded_engine).get_columns("opportunities")
    }
    assert "review_state" not in columns
    with downgraded_engine.connect() as connection:
        title = connection.scalar(
            text("SELECT title FROM opportunities WHERE id = :id"),
            {"id": opportunity_id},
        )
    assert title == "Existing decision candidate"
    downgraded_engine.dispose()
```

- [ ] **Step 2: Run the tests and confirm the new fields are absent**

Run:

```bash
apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_api.py::test_process_demo_endpoint \
  apps/api/tests/test_sqlite_schema_compatibility.py -v
```

Expected: FAIL because the model, response, compatibility columns, and index do not exist.

- [ ] **Step 3: Add the model and migration**

Add these fields to `Opportunity` immediately before `created_at`:

```python
    review_state: Mapped[str] = mapped_column(
        Text,
        default="new",
        server_default="new",
        index=True,
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
```

Create `apps/api/alembic/versions/0006_decision_workbench.py`:

```python
"""add opportunity decision fields

Revision ID: 0006_decision_workbench
Revises: 0005_scan_outcomes
Create Date: 2026-07-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_decision_workbench"
down_revision = "0005_scan_outcomes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "opportunities",
        sa.Column("review_state", sa.Text(), nullable=False, server_default="new"),
    )
    op.add_column("opportunities", sa.Column("review_note", sa.Text(), nullable=True))
    op.add_column(
        "opportunities",
        sa.Column("decision_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_opportunities_review_state",
        "opportunities",
        ["review_state"],
    )


def downgrade() -> None:
    op.drop_index("ix_opportunities_review_state", table_name="opportunities")
    op.drop_column("opportunities", "decision_updated_at")
    op.drop_column("opportunities", "review_note")
    op.drop_column("opportunities", "review_state")
```

- [ ] **Step 4: Add SQLite repair and typed decision input/output**

Extend `SQLITE_COMPAT_COLUMNS` and add a fixed index map in `session.py`:

```python
SQLITE_COMPAT_COLUMNS = {
    "scan_jobs": [
        ("signals_detected", "INTEGER NOT NULL DEFAULT 0"),
        ("clusters_created", "INTEGER NOT NULL DEFAULT 0"),
        ("opportunities_created", "INTEGER NOT NULL DEFAULT 0"),
        ("outcome_message", "TEXT"),
    ],
    "research_projects": [
        ("schedule_interval_hours", "INTEGER"),
        ("last_run_at", "DATETIME"),
        ("next_run_at", "DATETIME"),
        ("run_count", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "opportunities": [
        ("review_state", "TEXT NOT NULL DEFAULT 'new'"),
        ("review_note", "TEXT"),
        ("decision_updated_at", "DATETIME"),
    ],
}

SQLITE_COMPAT_INDEXES = {
    "opportunities": [
        ("ix_opportunities_review_state", "review_state"),
    ],
}
```

After the existing column loop, still inside `target_engine.begin()`, add:

```python
        for table_name, indexes in SQLITE_COMPAT_INDEXES.items():
            if table_name not in tables:
                continue
            existing_indexes = {
                index["name"] for index in inspect(target_engine).get_indexes(table_name)
            }
            for index_name, column_name in indexes:
                if index_name in existing_indexes:
                    continue
                connection.execute(
                    text(
                        f"CREATE INDEX IF NOT EXISTS {index_name} "
                        f"ON {table_name} ({column_name})"
                    )
                )
```

Create `apps/api/app/services/evidence_review/types.py`:

```python
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReviewState(StrEnum):
    NEW = "new"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    PROMISING = "promising"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"
    BUILD_CANDIDATE = "build_candidate"


class EvidenceReviewLabel(StrEnum):
    TRUE_SIGNAL = "true_signal"
    FALSE_POSITIVE = "false_positive"
    UNCLEAR = "unclear"
    DUPLICATE = "duplicate"
    NOT_ACTIONABLE = "not_actionable"
    SENSITIVE_RISK = "sensitive_risk"


class EvidenceReadinessLevel(StrEnum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


@dataclass(frozen=True)
class EvidenceReviewSnapshot:
    latest_stored_label: str | None = None
    review_label: EvidenceReviewLabel | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None
    history_count: int = 0
```

Import `ReviewState` into `schemas/api.py` and add:

```python
from app.services.evidence_review.types import ReviewState


class OpportunityReviewUpdate(BaseModel):
    review_state: ReviewState
    review_note: str | None = Field(default=None, max_length=1000)
```

Add to `OpportunityOut` before timestamps:

```python
    review_state: ReviewState = "new"
    review_note: str | None = None
    decision_updated_at: datetime | None = None
```

- [ ] **Step 5: Run focused tests and migration round-trip**

Run:

```bash
apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_api.py::test_process_demo_endpoint \
  apps/api/tests/test_sqlite_schema_compatibility.py -v
tmp_db="$(mktemp /tmp/tasksignal-v02-migration.XXXXXX)"
trap 'rm -f "$tmp_db"' EXIT
(cd apps/api && DATABASE_URL="sqlite:///$tmp_db" .venv/bin/alembic upgrade head)
(cd apps/api && DATABASE_URL="sqlite:///$tmp_db" .venv/bin/alembic downgrade 0005_scan_outcomes)
rm -f "$tmp_db"
trap - EXIT
```

Expected: focused tests pass; Alembic upgrades through `0006_decision_workbench`, downgrades to `0005_scan_outcomes`, and both commands exit 0.

- [ ] **Step 6: Commit the persistence checkpoint**

```bash
git add \
  apps/api/alembic/versions/0006_decision_workbench.py \
  apps/api/app/models/all_models.py \
  apps/api/app/db/session.py \
  apps/api/app/schemas/api.py \
  apps/api/app/services/evidence_review/types.py \
  apps/api/tests/test_sqlite_schema_compatibility.py \
  apps/api/tests/test_api.py
git commit -m "feat: persist opportunity decisions"
```

---
### Task 3: Build the evidence-review domain service

**Files:**
- Create: `apps/api/app/services/evidence_review/service.py`
- Create: `apps/api/tests/test_evidence_review_service.py`
- Modify: `apps/api/app/schemas/api.py:140-203`

**Interfaces:**
- Consumes: `EvidenceReviewLabel`, `EvidenceReadinessLevel`, `EvidenceReviewSnapshot`, `Label`, `NormalizedItem`, `ItemSignal`, `ClusterItem`, `Opportunity`, and `safe_source_url`.
- Produces: `get_label_history(db, item_id)`, `get_review_snapshots(db, item_ids)`, `calculate_evidence_readiness(items, snapshots)`, and `evaluation_summary(db)` plus fixed Pydantic response shapes.

- [ ] **Step 1: Write failing service tests for latest-label semantics, readiness, and evaluation**

Create `apps/api/tests/test_evidence_review_service.py`:

```python
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

from sqlalchemy import select

from app.models.all_models import ClusterItem, Label, NormalizedItem, Opportunity
from app.services.evidence_review.service import (
    calculate_evidence_readiness,
    evaluation_summary,
    get_review_snapshots,
)
from app.services.evidence_review.types import EvidenceReviewLabel, EvidenceReviewSnapshot
from app.workers.demo_pipeline import process_demo


def test_latest_unrecognized_label_does_not_fall_back(db_session) -> None:
    process_demo(db_session)
    item_id = db_session.scalar(select(NormalizedItem.id))
    assert item_id is not None
    timestamp = datetime(2026, 7, 9, tzinfo=UTC)
    db_session.add_all(
        [
            Label(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                item_id=item_id,
                label="true_signal",
                user_note="recognized",
                created_at=timestamp,
            ),
            Label(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                item_id=item_id,
                label="legacy_label",
                user_note="legacy newest",
                created_at=timestamp,
            ),
        ]
    )
    db_session.commit()

    snapshot = get_review_snapshots(db_session, [item_id])[item_id]

    assert snapshot.latest_stored_label == "legacy_label"
    assert snapshot.review_label is None
    assert snapshot.review_note is None
    assert snapshot.reviewed_at is None
    assert snapshot.history_count == 2


def test_readiness_uses_fixed_checks_and_sensitive_override() -> None:
    items = [
        SimpleNamespace(id=uuid4(), source="github", url="https://example.test/1"),
        SimpleNamespace(id=uuid4(), source="github", url="https://example.test/2"),
        SimpleNamespace(id=uuid4(), source="hackernews", url="https://example.test/3"),
        SimpleNamespace(id=uuid4(), source="hackernews", url="https://example.test/4"),
        SimpleNamespace(id=uuid4(), source="hackernews", url="javascript:alert(1)"),
    ]
    snapshots = {
        items[0].id: EvidenceReviewSnapshot(
            latest_stored_label="true_signal",
            review_label=EvidenceReviewLabel.TRUE_SIGNAL,
            history_count=1,
        ),
        items[1].id: EvidenceReviewSnapshot(
            latest_stored_label="true_signal",
            review_label=EvidenceReviewLabel.TRUE_SIGNAL,
            history_count=1,
        ),
        items[2].id: EvidenceReviewSnapshot(
            latest_stored_label="sensitive_risk",
            review_label=EvidenceReviewLabel.SENSITIVE_RISK,
            history_count=1,
        ),
    }

    readiness = calculate_evidence_readiness(items, snapshots)

    assert readiness.evidence_count == 5
    assert readiness.source_count == 2
    assert readiness.safe_url_count == 4
    assert readiness.reviewed_count == 3
    assert readiness.source_url_coverage == 0.8
    assert readiness.human_review_coverage == 0.6
    assert all(readiness.checks.model_dump().values())
    assert readiness.level == "weak"
    assert readiness.gaps == [
        "Resolve or exclude evidence marked sensitive risk before advancing."
    ]


def readiness_items(
    count: int,
    sources: tuple[str, ...],
    safe_url_count: int,
) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            id=uuid4(),
            source=sources[index % len(sources)],
            url=(
                f"https://example.test/{index}"
                if index < safe_url_count
                else "javascript:alert(1)"
            ),
        )
        for index in range(count)
    ]


def test_readiness_levels_and_deterministic_gap_templates() -> None:
    strong_items = readiness_items(6, ("github", "hackernews"), 6)
    strong_snapshots = {
        item.id: EvidenceReviewSnapshot(
            latest_stored_label="true_signal",
            review_label=EvidenceReviewLabel.TRUE_SIGNAL,
            history_count=1,
        )
        for item in strong_items[:3]
    }
    strong = calculate_evidence_readiness(strong_items, strong_snapshots)
    assert strong.level == "strong"
    assert strong.passed_checks == [
        "enough_evidence",
        "source_diversity",
        "source_url_coverage",
        "human_review_coverage",
    ]
    assert strong.gaps == []

    medium_items = readiness_items(5, ("github",), 4)
    medium = calculate_evidence_readiness(medium_items, {})
    assert medium.level == "medium"
    assert medium.passed_checks == ["enough_evidence", "source_url_coverage"]
    assert medium.gaps == [
        "Add evidence from 1 more source.",
        "Review 3 more evidence items.",
    ]

    weak_items = readiness_items(1, ("github",), 0)
    weak = calculate_evidence_readiness(weak_items, {})
    assert weak.level == "weak"
    assert weak.passed_checks == []
    assert weak.gaps == [
        "Collect 4 more evidence items.",
        "Add evidence from 1 more source.",
        "Increase safe source URL coverage to at least 80%.",
        "Review 1 more evidence item.",
    ]


def test_empty_evaluation_is_zeroed(db_session) -> None:
    summary = evaluation_summary(db_session)

    assert summary.total_reviewable_items == 0
    assert summary.reviewed_items == 0
    assert summary.review_coverage == 0.0
    assert summary.label_counts.model_dump() == {
        label.value: 0 for label in EvidenceReviewLabel
    }
    assert summary.unrecognized_latest_labels == 0
    assert summary.precision_on_reviewed_positives is None
    assert summary.by_source == {}
    assert summary.by_signal_type == {}


def test_evaluation_counts_reviewed_items_and_precision_without_duplicates(db_session) -> None:
    process_demo(db_session)
    opportunity = db_session.scalar(
        select(Opportunity).order_by(Opportunity.opportunity_score.desc())
    )
    assert opportunity is not None
    item_ids = list(
        db_session.scalars(
            select(ClusterItem.item_id).where(
                ClusterItem.cluster_id == opportunity.cluster_id
            )
        )
    )
    assert len(item_ids) >= 2
    baseline = evaluation_summary(db_session)
    db_session.add(
        Opportunity(
            **{
                column.name: getattr(opportunity, column.name)
                for column in Opportunity.__table__.columns
                if column.name != "id"
            }
        )
    )
    db_session.add_all(
        [
            Label(item_id=item_ids[0], label="true_signal", user_note=None),
            Label(item_id=item_ids[1], label="false_positive", user_note=None),
        ]
    )
    db_session.commit()

    summary = evaluation_summary(db_session)

    assert summary.total_reviewable_items == baseline.total_reviewable_items
    assert summary.reviewed_items == 2
    assert summary.label_counts.true_signal == 1
    assert summary.label_counts.false_positive == 1
    assert summary.precision_on_reviewed_positives == 0.5
    assert summary.unrecognized_latest_labels == 0
    assert list(summary.by_source) == sorted(summary.by_source)
    assert list(summary.by_signal_type) == sorted(summary.by_signal_type)
    assert sum(row.total_items for row in summary.by_source.values()) == (
        summary.total_reviewable_items
    )
    assert sum(row.total_items for row in summary.by_signal_type.values()) == (
        summary.total_reviewable_items
    )
    assert summary.selection_bias_warning == (
        "Metrics describe only manually reviewed evidence and may not represent "
        "all detected items."
    )
```

- [ ] **Step 2: Run the service tests and confirm the module/contracts do not exist**

Run:

```bash
apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_evidence_review_service.py -v
```

Expected: collection FAIL because `app.services.evidence_review.service` and the response schemas are absent.

- [ ] **Step 3: Add the exact readiness and evaluation schemas**

Add these models to `schemas/api.py` after `ItemOut`, importing the shared enums from `app.services.evidence_review.types`:

```python
class EvidenceReadinessChecksOut(BaseModel):
    enough_evidence: bool
    source_diversity: bool
    source_url_coverage: bool
    human_review_coverage: bool


class EvidenceReadinessOut(BaseModel):
    level: EvidenceReadinessLevel
    evidence_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    safe_url_count: int = Field(ge=0)
    reviewed_count: int = Field(ge=0)
    source_url_coverage: float = Field(ge=0.0, le=1.0)
    human_review_coverage: float = Field(ge=0.0, le=1.0)
    checks: EvidenceReadinessChecksOut
    passed_checks: list[str]
    gaps: list[str]


class EvidenceLabelCountsOut(BaseModel):
    true_signal: int = Field(default=0, ge=0)
    false_positive: int = Field(default=0, ge=0)
    unclear: int = Field(default=0, ge=0)
    duplicate: int = Field(default=0, ge=0)
    not_actionable: int = Field(default=0, ge=0)
    sensitive_risk: int = Field(default=0, ge=0)


class EvaluationSliceOut(BaseModel):
    total_items: int = Field(ge=0)
    reviewed_items: int = Field(ge=0)
    review_coverage: float = Field(ge=0.0, le=1.0)
    label_counts: EvidenceLabelCountsOut
    precision_on_reviewed_positives: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )


class EvaluationOut(BaseModel):
    total_reviewable_items: int = Field(ge=0)
    reviewed_items: int = Field(ge=0)
    review_coverage: float = Field(ge=0.0, le=1.0)
    label_counts: EvidenceLabelCountsOut
    unrecognized_latest_labels: int = Field(ge=0)
    precision_on_reviewed_positives: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )
    by_source: dict[str, EvaluationSliceOut]
    by_signal_type: dict[str, EvaluationSliceOut]
    selection_bias_warning: str


class LabelCreate(BaseModel):
    item_id: UUID
    label: EvidenceReviewLabel
    user_note: str | None = Field(default=None, max_length=500)


class LabelOut(BaseModel):
    id: UUID
    item_id: UUID
    label: str
    user_note: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

Remove the old unconstrained `LabelCreate`. Extend `ItemOut` with:

```python
    review_label: EvidenceReviewLabel | None = None
    review_note: str | None = None
    reviewed_at: datetime | None = None
    review_history_count: int = 0
```

- [ ] **Step 4: Implement the evidence-review service**

Create `apps/api/app/services/evidence_review/service.py`:

```python
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from math import ceil
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.all_models import (
    ClusterItem,
    ItemSignal,
    Label,
    NormalizedItem,
    Opportunity,
)
from app.schemas.api import (
    EvaluationOut,
    EvaluationSliceOut,
    EvidenceLabelCountsOut,
    EvidenceReadinessChecksOut,
    EvidenceReadinessOut,
)
from app.services.evidence_review.types import (
    EvidenceReadinessLevel,
    EvidenceReviewLabel,
    EvidenceReviewSnapshot,
)
from app.services.ingestion.normalization import safe_source_url


CHECK_ORDER = (
    "enough_evidence",
    "source_diversity",
    "source_url_coverage",
    "human_review_coverage",
)
SELECTION_BIAS_WARNING = (
    "Metrics describe only manually reviewed evidence and may not represent "
    "all detected items."
)
ReviewableRecord = tuple[NormalizedItem, ItemSignal | None, EvidenceReviewSnapshot]


def _count_text(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def get_label_history(db: Session, item_id: UUID) -> list[Label]:
    return list(
        db.scalars(
            select(Label)
            .where(Label.item_id == item_id)
            .order_by(Label.created_at.desc(), Label.id.desc())
        )
    )


def get_review_snapshots(
    db: Session,
    item_ids: Collection[UUID],
) -> dict[UUID, EvidenceReviewSnapshot]:
    unique_ids = set(item_ids)
    if not unique_ids:
        return {}
    rows = list(
        db.scalars(
            select(Label)
            .where(Label.item_id.in_(unique_ids))
            .order_by(Label.created_at.desc(), Label.id.desc())
        )
    )
    latest: dict[UUID, Label] = {}
    history_counts: dict[UUID, int] = defaultdict(int)
    for row in rows:
        history_counts[row.item_id] += 1
        latest.setdefault(row.item_id, row)

    snapshots: dict[UUID, EvidenceReviewSnapshot] = {}
    for item_id in unique_ids:
        row = latest.get(item_id)
        recognized: EvidenceReviewLabel | None = None
        if row is not None:
            try:
                recognized = EvidenceReviewLabel(row.label)
            except ValueError:
                recognized = None
        snapshots[item_id] = EvidenceReviewSnapshot(
            latest_stored_label=row.label if row else None,
            review_label=recognized,
            review_note=row.user_note if row and recognized else None,
            reviewed_at=row.created_at if row and recognized else None,
            history_count=history_counts[item_id],
        )
    return snapshots


def calculate_evidence_readiness(
    items: Sequence[NormalizedItem],
    snapshots: Mapping[UUID, EvidenceReviewSnapshot],
) -> EvidenceReadinessOut:
    unique_items = {item.id: item for item in items}
    evidence_count = len(unique_items)
    source_count = len(
        {item.source.strip() for item in unique_items.values() if item.source.strip()}
    )
    safe_url_count = sum(
        bool(safe_source_url(item.url, fallback="")) for item in unique_items.values()
    )
    reviewed_count = sum(
        snapshots.get(item_id, EvidenceReviewSnapshot()).review_label is not None
        for item_id in unique_items
    )
    source_url_coverage = safe_url_count / evidence_count if evidence_count else 0.0
    human_review_coverage = reviewed_count / evidence_count if evidence_count else 0.0
    sensitive_risk = any(
        snapshots.get(item_id, EvidenceReviewSnapshot()).review_label
        == EvidenceReviewLabel.SENSITIVE_RISK
        for item_id in unique_items
    )
    checks = EvidenceReadinessChecksOut(
        enough_evidence=evidence_count >= 5,
        source_diversity=source_count >= 2,
        source_url_coverage=evidence_count > 0 and source_url_coverage >= 0.8,
        human_review_coverage=evidence_count > 0 and human_review_coverage >= 0.5,
    )
    check_values = checks.model_dump()
    passed_checks = [name for name in CHECK_ORDER if check_values[name]]
    gaps: list[str] = []
    if not checks.enough_evidence:
        remaining = 5 - evidence_count
        noun = _count_text(remaining, "item", "items")
        gaps.append(f"Collect {remaining} more evidence {noun}.")
    if not checks.source_diversity:
        remaining = 2 - source_count
        noun = _count_text(remaining, "source", "sources")
        gaps.append(f"Add evidence from {remaining} more {noun}.")
    if not checks.source_url_coverage:
        gaps.append("Increase safe source URL coverage to at least 80%.")
    if not checks.human_review_coverage:
        remaining = max(1, ceil(evidence_count * 0.5) - reviewed_count)
        noun = _count_text(remaining, "item", "items")
        gaps.append(f"Review {remaining} more evidence {noun}.")
    if sensitive_risk:
        gaps.append("Resolve or exclude evidence marked sensitive risk before advancing.")

    passed_count = len(passed_checks)
    if sensitive_risk:
        level = EvidenceReadinessLevel.WEAK
    elif passed_count == len(CHECK_ORDER):
        level = EvidenceReadinessLevel.STRONG
    elif passed_count >= 2:
        level = EvidenceReadinessLevel.MEDIUM
    else:
        level = EvidenceReadinessLevel.WEAK

    return EvidenceReadinessOut(
        level=level,
        evidence_count=evidence_count,
        source_count=source_count,
        safe_url_count=safe_url_count,
        reviewed_count=reviewed_count,
        source_url_coverage=source_url_coverage,
        human_review_coverage=human_review_coverage,
        checks=checks,
        passed_checks=passed_checks,
        gaps=gaps,
    )


def _label_counts(records: Sequence[ReviewableRecord]) -> EvidenceLabelCountsOut:
    counts = {label.value: 0 for label in EvidenceReviewLabel}
    for _item, _signal, snapshot in records:
        if snapshot.review_label is not None:
            counts[snapshot.review_label.value] += 1
    return EvidenceLabelCountsOut(**counts)


def _evaluation_slice(records: Sequence[ReviewableRecord]) -> EvaluationSliceOut:
    total = len(records)
    reviewed = sum(snapshot.review_label is not None for _, _, snapshot in records)
    counts = _label_counts(records)
    precision_denominator = counts.true_signal + counts.false_positive
    precision = (
        counts.true_signal / precision_denominator if precision_denominator else None
    )
    return EvaluationSliceOut(
        total_items=total,
        reviewed_items=reviewed,
        review_coverage=reviewed / total if total else 0.0,
        label_counts=counts,
        precision_on_reviewed_positives=precision,
    )


def evaluation_summary(db: Session) -> EvaluationOut:
    rows = db.execute(
        select(NormalizedItem, ItemSignal)
        .join(ClusterItem, ClusterItem.item_id == NormalizedItem.id)
        .join(Opportunity, Opportunity.cluster_id == ClusterItem.cluster_id)
        .join(ItemSignal, ItemSignal.item_id == NormalizedItem.id, isouter=True)
    ).all()
    deduplicated: dict[UUID, tuple[NormalizedItem, ItemSignal | None]] = {}
    for item, signal in rows:
        deduplicated.setdefault(item.id, (item, signal))
    snapshots = get_review_snapshots(db, deduplicated)
    records: list[ReviewableRecord] = [
        (item, signal, snapshots.get(item_id, EvidenceReviewSnapshot()))
        for item_id, (item, signal) in deduplicated.items()
    ]
    overall = _evaluation_slice(records)
    by_source_records: dict[str, list[ReviewableRecord]] = defaultdict(list)
    by_signal_records: dict[str, list[ReviewableRecord]] = defaultdict(list)
    for record in records:
        item, signal, _snapshot = record
        by_source_records[item.source.strip() or "unknown"].append(record)
        signal_type = signal.signal_type.strip() if signal and signal.signal_type else ""
        by_signal_records[signal_type or "unknown"].append(record)

    return EvaluationOut(
        total_reviewable_items=overall.total_items,
        reviewed_items=overall.reviewed_items,
        review_coverage=overall.review_coverage,
        label_counts=overall.label_counts,
        unrecognized_latest_labels=sum(
            snapshot.latest_stored_label is not None and snapshot.review_label is None
            for _, _, snapshot in records
        ),
        precision_on_reviewed_positives=overall.precision_on_reviewed_positives,
        by_source={
            key: _evaluation_slice(by_source_records[key])
            for key in sorted(by_source_records)
        },
        by_signal_type={
            key: _evaluation_slice(by_signal_records[key])
            for key in sorted(by_signal_records)
        },
        selection_bias_warning=SELECTION_BIAS_WARNING,
    )
```

- [ ] **Step 5: Run the service tests and backend lint**

Run:

```bash
apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_evidence_review_service.py -v
apps/api/.venv/bin/ruff check \
  apps/api/app/services/evidence_review \
  apps/api/app/schemas/api.py \
  apps/api/tests/test_evidence_review_service.py
```

Expected: five service tests pass and ruff reports no errors.

- [ ] **Step 6: Commit the domain-service checkpoint**

```bash
git add \
  apps/api/app/services/evidence_review/service.py \
  apps/api/app/schemas/api.py \
  apps/api/tests/test_evidence_review_service.py
git commit -m "feat: add evidence review evaluation service"
```

---

### Task 4: Expose decisions, evidence reviews, evaluation, and safe exports

**Files:**
- Create: `apps/api/tests/test_decision_workbench.py`
- Modify: `apps/api/app/schemas/api.py:158-203`
- Modify: `apps/api/app/api/routes.py:8-55,518-828,1110-1330`
- Modify: `apps/api/tests/test_api.py:450-620`
- Modify: `skills/tasksignal-opportunity-builder/scripts/check_task_pack.py:7-15`

**Interfaces:**
- Consumes: Task 2 decision fields and Task 3 service functions/schemas.
- Produces: `PATCH /api/opportunities/{id}/review`, optional opportunity-state filtering, typed append-only labels/history, `GET /api/evaluation`, enriched `OpportunityOut`, enriched `TaskPackOut`, and required `## Decision Context` export section.

- [ ] **Step 1: Write failing API and export tests**

Create `apps/api/tests/test_decision_workbench.py`:

```python
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.api import routes
from app.db.session import engine
from app.models.all_models import Label


def first_opportunity(client) -> dict:
    client.post("/api/process/demo")
    return client.get("/api/opportunities").json()[0]


def test_opportunity_review_persists_filters_and_survives_regeneration(client) -> None:
    opportunity = first_opportunity(client)
    response = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={
            "review_state": "promising",
            "review_note": "Validate with maintainers.",
        },
    )

    assert response.status_code == 200
    reviewed = response.json()
    assert reviewed["review_state"] == "promising"
    assert reviewed["review_note"] == "Validate with maintainers."
    assert reviewed["decision_updated_at"] is not None
    decision_updated_at = reviewed["decision_updated_at"]
    assert client.get("/api/opportunities?review_state=promising").json()[0]["id"] == (
        opportunity["id"]
    )
    assert client.get("/api/opportunities?review_state=rejected").json() == []

    regenerated = client.post(
        f"/api/opportunities/{opportunity['id']}/regenerate"
    ).json()
    assert regenerated["review_state"] == "promising"
    assert regenerated["review_note"] == "Validate with maintainers."
    assert regenerated["decision_updated_at"] == decision_updated_at

    reset = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "new", "review_note": None},
    ).json()
    assert reset["review_state"] == "new"
    assert reset["review_note"] is None
    assert reset["decision_updated_at"] >= decision_updated_at


def test_opportunity_review_validation_and_missing_record(client) -> None:
    opportunity = first_opportunity(client)
    invalid_state = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "approved", "review_note": None},
    )
    oversized = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "promising", "review_note": "x" * 1001},
    )
    missing = client.patch(
        "/api/opportunities/00000000-0000-0000-0000-000000000000/review",
        json={"review_state": "promising", "review_note": None},
    )

    assert invalid_state.status_code == 422
    assert oversized.status_code == 422
    assert missing.status_code == 404


def test_prompt_enhancement_does_not_change_decision(client, monkeypatch) -> None:
    opportunity = first_opportunity(client)
    reviewed = client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "promising", "review_note": "Keep this decision."},
    ).json()
    monkeypatch.setattr(routes.settings, "operator_scan_token", "test-operator-token")
    monkeypatch.setattr(
        routes,
        "enhance_prompt",
        lambda prompt: ("openai", "test-model", f"{prompt}\n\nEnhanced."),
    )

    response = client.post(
        f"/api/opportunities/{opportunity['id']}/enhance?apply=true",
        headers={"X-Operator-Scan-Token": "test-operator-token"},
    )
    refreshed = client.get(f"/api/opportunities/{opportunity['id']}").json()

    assert response.status_code == 200
    assert refreshed["review_state"] == "promising"
    assert refreshed["review_note"] == "Keep this decision."
    assert refreshed["decision_updated_at"] == reviewed["decision_updated_at"]


def test_evidence_reviews_are_append_only_and_legacy_latest_is_unrecognized(client) -> None:
    opportunity = first_opportunity(client)
    item_id = opportunity["evidence_items"][0]["id"]
    first = client.post(
        "/api/labels",
        json={"item_id": item_id, "label": "true_signal", "user_note": "Useful."},
    )
    second = client.post(
        "/api/labels",
        json={"item_id": item_id, "label": "unclear", "user_note": None},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    history = client.get(f"/api/items/{item_id}/labels").json()
    assert [row["label"] for row in history] == ["unclear", "true_signal"]

    with Session(engine) as session:
        session.add(
            Label(
                id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
                item_id=UUID(item_id),
                label="legacy_label",
                user_note="Do not export legacy note.",
                created_at=datetime(2030, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()

    refreshed = client.get(f"/api/opportunities/{opportunity['id']}").json()
    evidence = next(item for item in refreshed["evidence_items"] if item["id"] == item_id)
    assert evidence["review_label"] is None
    assert evidence["review_note"] is None
    assert evidence["review_history_count"] == 3
    evaluation = client.get("/api/evaluation").json()
    assert evaluation["unrecognized_latest_labels"] == 1


def test_decision_context_exports_state_and_readiness_without_local_notes(client) -> None:
    opportunity = first_opportunity(client)
    item_id = opportunity["evidence_items"][0]["id"]
    opportunity_note = "LOCAL-OPPORTUNITY-NOTE-MUST-NOT-EXPORT"
    evidence_note = "LOCAL-EVIDENCE-NOTE-MUST-NOT-EXPORT"
    client.patch(
        f"/api/opportunities/{opportunity['id']}/review",
        json={"review_state": "build_candidate", "review_note": opportunity_note},
    )
    client.post(
        "/api/labels",
        json={
            "item_id": item_id,
            "label": "true_signal",
            "user_note": evidence_note,
        },
    )

    evidence_markdown = client.get(
        f"/api/opportunities/{opportunity['id']}/evidence.md"
    ).text
    task_pack_response = client.get(
        f"/api/opportunities/{opportunity['id']}/task-pack.json"
    )
    task_pack = task_pack_response.json()

    assert task_pack_response.status_code == 200
    assert task_pack["review_state"] == "build_candidate"
    assert task_pack["evidence_readiness"]["level"] in {"weak", "medium", "strong"}
    assert "## Decision Context" in task_pack["markdown"]
    assert "## Decision Context" in evidence_markdown
    serialized = evidence_markdown + task_pack["markdown"] + str(task_pack)
    assert opportunity_note not in serialized
    assert evidence_note not in serialized


def test_label_write_rejects_unknown_missing_and_oversized_inputs(client) -> None:
    opportunity = first_opportunity(client)
    item_id = opportunity["evidence_items"][0]["id"]
    unknown = client.post(
        "/api/labels",
        json={"item_id": item_id, "label": "useful", "user_note": None},
    )
    missing = client.post(
        "/api/labels",
        json={
            "item_id": "00000000-0000-0000-0000-000000000000",
            "label": "true_signal",
            "user_note": None,
        },
    )
    missing_history = client.get(
        "/api/items/00000000-0000-0000-0000-000000000000/labels"
    )
    oversized = client.post(
        "/api/labels",
        json={"item_id": item_id, "label": "true_signal", "user_note": "x" * 501},
    )

    assert unknown.status_code == 422
    assert missing.status_code == 404
    assert missing_history.status_code == 404
    assert oversized.status_code == 422
```

- [ ] **Step 2: Run the tests and confirm the routes/serialization are absent**

Run:

```bash
apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_decision_workbench.py -v
```

Expected: FAIL on missing review/evaluation routes and missing enriched fields.

- [ ] **Step 3: Complete the response contracts**

Extend `OpportunityOut` and replace `TaskPackOut` with these exact additions:

```python
class OpportunityOut(BaseModel):
    id: UUID
    cluster_id: UUID
    title: str
    problem_statement: str
    target_user: str
    current_workaround: str
    suggested_mvp: str
    why_now: str
    feasibility_score: float
    opportunity_score: float
    competition_notes: str
    scoring_breakdown_json: dict
    generated_prompt: str
    review_state: ReviewState
    review_note: str | None
    decision_updated_at: datetime | None
    created_at: datetime
    updated_at: datetime
    evidence_items: list[ItemOut] = []
    signal_count: int = 0
    top_source: str = "fixture"
    evidence_readiness: EvidenceReadinessOut
    model_config = ConfigDict(from_attributes=True)


class TaskPackOut(BaseModel):
    opportunity_id: UUID
    title: str
    problem: str
    suggested_mvp: str
    codex_prompt: str
    markdown: str
    evidence_urls: list[str]
    acceptance_criteria: list[str]
    privacy_constraints: list[str]
    review_state: ReviewState
    evidence_readiness: EvidenceReadinessOut
```

In `test_evidence_bundle_export_drops_unsafe_source_urls` in
`apps/api/tests/test_api.py`, add these exact keyword arguments to the manual
`OpportunityOut(...)` fixture after `generated_prompt` and after `top_source`,
respectively:

```python
        review_state="new",
        review_note=None,
        decision_updated_at=None,
```

```python
        evidence_readiness={
            "level": "weak",
            "evidence_count": 1,
            "source_count": 1,
            "safe_url_count": 0,
            "reviewed_count": 0,
            "source_url_coverage": 0.0,
            "human_review_coverage": 0.0,
            "checks": {
                "enough_evidence": False,
                "source_diversity": False,
                "source_url_coverage": False,
                "human_review_coverage": False,
            },
            "passed_checks": [],
            "gaps": [
                "Collect 4 more evidence items.",
                "Add evidence from 1 more source.",
                "Increase safe source URL coverage to at least 80%.",
                "Review 1 more evidence item.",
            ],
        },
```

- [ ] **Step 4: Enrich item and opportunity serialization in one query per label set**

Import `SQLAlchemyError`, the new schemas/types, and the Task 3 service functions. Replace the serializers with:

```python
def item_to_out(
    item: NormalizedItem,
    signal: ItemSignal | None = None,
    review: EvidenceReviewSnapshot | None = None,
) -> ItemOut:
    review = review or EvidenceReviewSnapshot()
    return ItemOut(
        id=item.id,
        source=item.source,
        external_id=item.external_id,
        url=item.url,
        title=item.title,
        body=item.body,
        score=item.score,
        comments_count=item.comments_count,
        created_at=item.created_at,
        tags=item.tags,
        signal_type=signal.signal_type if signal else None,
        pain_score=signal.pain_score if signal else None,
        task_concreteness_score=signal.task_concreteness_score if signal else None,
        buying_intent_score=signal.buying_intent_score if signal else None,
        evidence_spans=signal.evidence_spans_json if signal else [],
        review_label=review.review_label,
        review_note=review.review_note,
        reviewed_at=review.reviewed_at,
        review_history_count=review.history_count,
    )


def items_to_out(
    db: Session,
    rows: list[tuple[NormalizedItem, ItemSignal | None]],
) -> list[ItemOut]:
    snapshots = get_review_snapshots(db, [item.id for item, _signal in rows])
    return [
        item_to_out(item, signal, snapshots.get(item.id))
        for item, signal in rows
    ]


def opportunity_to_out(db: Session, opportunity: Opportunity) -> OpportunityOut:
    rows = cluster_signal_rows(db, opportunity.cluster_id)
    items = [item for item, _signal in rows]
    snapshots = get_review_snapshots(db, [item.id for item in items])
    evidence = [
        item_to_out(item, signal, snapshots.get(item.id))
        for item, signal in rows
    ]
    top_source = max(
        {item.source for item in items},
        key=lambda source: sum(item.source == source for item in items),
        default="fixture",
    )
    return OpportunityOut(
        **{
            column.name: getattr(opportunity, column.name)
            for column in Opportunity.__table__.columns
        },
        evidence_items=evidence,
        signal_count=len(evidence),
        top_source=top_source,
        evidence_readiness=calculate_evidence_readiness(items, snapshots),
    )
```

Use `items_to_out(db, list(rows))` in `/items`; use one snapshot in `/items/{id}`. Keep existing ordering and 100-item limit unchanged.

- [ ] **Step 5: Replace existing list/label handlers and add the new routes with rollback**

Add `commit_review_write`; replace the existing `list_opportunities` and
`create_label` handlers in place; add the new PATCH, history, and evaluation
handlers. Do not leave duplicate `GET /opportunities` or `POST /labels` route
registrations.

```python
def commit_review_write(db: Session, failure_detail: str) -> None:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=failure_detail) from exc


@router.get("/opportunities", response_model=list[OpportunityOut])
def list_opportunities(
    review_state: ReviewState | None = None,
    db: Session = Depends(get_db),
) -> list[OpportunityOut]:
    query = select(Opportunity).order_by(Opportunity.opportunity_score.desc())
    if review_state is not None:
        query = query.where(Opportunity.review_state == review_state.value)
    return [opportunity_to_out(db, item) for item in db.scalars(query).all()]


@router.patch(
    "/opportunities/{opportunity_id}/review",
    response_model=OpportunityOut,
)
def update_opportunity_review(
    opportunity_id: UUID,
    payload: OpportunityReviewUpdate,
    db: Session = Depends(get_db),
) -> OpportunityOut:
    opportunity = db.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    note = payload.review_note.strip() if payload.review_note else None
    opportunity.review_state = payload.review_state.value
    opportunity.review_note = note or None
    opportunity.decision_updated_at = datetime.now(UTC)
    commit_review_write(db, "Could not save the opportunity decision.")
    db.refresh(opportunity)
    return opportunity_to_out(db, opportunity)


@router.post("/labels", response_model=LabelOut)
def create_label(payload: LabelCreate, db: Session = Depends(get_db)) -> LabelOut:
    if db.get(NormalizedItem, payload.item_id) is None:
        raise HTTPException(status_code=404, detail="Item not found")
    note = payload.user_note.strip() if payload.user_note else None
    label = Label(
        item_id=payload.item_id,
        label=payload.label.value,
        user_note=note or None,
    )
    db.add(label)
    commit_review_write(db, "Could not save the evidence review.")
    db.refresh(label)
    return LabelOut.model_validate(label)


@router.get("/items/{item_id}/labels", response_model=list[LabelOut])
def list_item_labels(item_id: UUID, db: Session = Depends(get_db)) -> list[LabelOut]:
    if db.get(NormalizedItem, item_id) is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return [LabelOut.model_validate(row) for row in get_label_history(db, item_id)]


@router.get("/evaluation", response_model=EvaluationOut)
def get_evaluation(db: Session = Depends(get_db)) -> EvaluationOut:
    return evaluation_summary(db)
```

Every identical save and reset to `new` updates `decision_updated_at`; regeneration and enhancement do not touch decision fields.

- [ ] **Step 6: Add deterministic Decision Context to exports and task-pack JSON**

Add:

```python
DECISION_CHECK_LABELS = {
    "enough_evidence": "Enough evidence",
    "source_diversity": "Source diversity",
    "source_url_coverage": "Safe source URL coverage",
    "human_review_coverage": "Human review coverage",
}


def decision_context_lines(opportunity: OpportunityOut) -> list[str]:
    readiness = opportunity.evidence_readiness
    lines = [
        "## Decision Context",
        "",
        f"- Review state: {opportunity.review_state.value}",
        f"- Evidence readiness: {readiness.level.value}",
        f"- Human review coverage: {readiness.human_review_coverage:.0%}",
        "- Readiness checks:",
    ]
    check_values = readiness.checks.model_dump()
    for key, label in DECISION_CHECK_LABELS.items():
        lines.append(f"  - {label}: {'passed' if check_values[key] else 'needs work'}")
    lines.append("- Readiness gaps:")
    lines.extend(f"  - {gap}" for gap in readiness.gaps)
    if not readiness.gaps:
        lines.append("  - None.")
    return lines
```

Insert `*decision_context_lines(opportunity), ""` after the opportunity summary in `evidence_bundle_markdown` and after `## Evidence Score` content in `task_pack_markdown`. Add to `task_pack_json`:

```python
        review_state=opportunity.review_state,
        evidence_readiness=opportunity.evidence_readiness,
```

Do not change `/opportunities/{id}/export.md`; it remains the generated prompt only. Add `"## Decision Context"` between `"## Evidence Score"` and `"## Evidence"` in the checker `REQUIRED_SECTIONS` list.

- [ ] **Step 7: Run API, export, contract, and privacy tests**

In every valid task-pack fixture in `apps/api/tests/test_first_run_smoke.py`,
insert this non-empty section after the Evidence Score content and before
Evidence:

```python
            "## Decision Context",
            "- Review state: new",
```

Change `smoke_result()["task_pack_required_sections"]` and every exact valid
section-count assertion from `7` to `8`. Leave intentionally incomplete fixture
packs incomplete so their failure assertions remain meaningful.

Run:

```bash
apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_decision_workbench.py \
  apps/api/tests/test_api.py \
  apps/api/tests/test_first_run_smoke.py -v
apps/api/.venv/bin/ruff check \
  apps/api/app/api/routes.py \
  apps/api/app/schemas/api.py \
  apps/api/tests/test_decision_workbench.py \
  skills/tasksignal-opportunity-builder/scripts/check_task_pack.py
```

Expected: review/filter/label/history/evaluation/export tests pass and contract assertions report eight required sections.

- [ ] **Step 8: Commit the backend workflow checkpoint**

```bash
git add \
  apps/api/app/api/routes.py \
  apps/api/app/schemas/api.py \
  apps/api/tests/test_decision_workbench.py \
  apps/api/tests/test_api.py \
  apps/api/tests/test_first_run_smoke.py \
  skills/tasksignal-opportunity-builder/scripts/check_task_pack.py
git commit -m "feat: add TaskSignal decision review API"
```

---

### Task 5: Add frontend contracts, metadata, errors, and shared form primitives

**Files:**
- Create: `apps/web/src/lib/review.ts`
- Create: `apps/web/src/lib/api-error.ts`
- Create: `apps/web/tests/api.test.ts`
- Modify: `apps/web/src/lib/types.ts:1-215`
- Modify: `apps/web/src/lib/api.ts:1-112`
- Modify: `apps/web/src/components/ui.tsx:1-205`
- Modify: `apps/web/src/features/opportunity-detail.tsx:54-68`

**Interfaces:**
- Consumes: exact backend response shapes from Tasks 3-4.
- Produces: TypeScript review/evaluation types, ordered display metadata, `apiErrorMessage`, `Textarea`, and API methods used by all v0.2 frontend surfaces.

- [ ] **Step 1: Write failing API contract tests**

Create `apps/web/tests/api.test.ts`:

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../src/lib/api";


describe("decision workbench API", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("encodes an optional opportunity state filter", async () => {
    const fetchMock = vi.fn(async () => Response.json([]));
    vi.stubGlobal("fetch", fetchMock);

    await api.opportunities("needs_more_evidence");

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/opportunities?review_state=needs_more_evidence",
      expect.any(Object),
    );
  });

  it("sends the exact opportunity review patch", async () => {
    const fetchMock = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetchMock);

    await api.updateOpportunityReview("opportunity-1", {
      review_state: "promising",
      review_note: "Validate with maintainers.",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/opportunities/opportunity-1/review",
      expect.objectContaining({
        method: "PATCH",
        body: JSON.stringify({
          review_state: "promising",
          review_note: "Validate with maintainers.",
        }),
      }),
    );
  });

  it("writes evidence reviews and reads history and evaluation", async () => {
    const fetchMock = vi.fn(async () => Response.json({}));
    vi.stubGlobal("fetch", fetchMock);

    await api.createEvidenceReview({
      item_id: "item-1",
      label: "true_signal",
      user_note: null,
    });
    await api.itemReviewHistory("item-1");
    await api.evaluation();

    expect(fetchMock.mock.calls.map(([input]) => String(input))).toEqual([
      "http://localhost:8000/api/labels",
      "http://localhost:8000/api/items/item-1/labels",
      "http://localhost:8000/api/evaluation",
    ]);
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          item_id: "item-1",
          label: "true_signal",
          user_note: null,
        }),
      }),
    );
  });
});
```

- [ ] **Step 2: Run the API tests and confirm the new methods are absent**

Run:

```bash
PATH="/opt/homebrew/opt/node@20/bin:$PATH" \
  npm --prefix apps/web test -- --run tests/api.test.ts
```

Expected: TypeScript/Vitest FAIL because the new API methods and types do not exist.

- [ ] **Step 3: Add exact frontend domain types**

Add to `types.ts`:

```typescript
export type ReviewState =
  | "new"
  | "needs_more_evidence"
  | "promising"
  | "rejected"
  | "duplicate"
  | "build_candidate";

export type EvidenceReviewLabel =
  | "true_signal"
  | "false_positive"
  | "unclear"
  | "duplicate"
  | "not_actionable"
  | "sensitive_risk";

export type EvidenceReadinessLevel = "weak" | "medium" | "strong";
export type EvidenceReadinessCheck =
  | "enough_evidence"
  | "source_diversity"
  | "source_url_coverage"
  | "human_review_coverage";

export type EvidenceReadiness = {
  level: EvidenceReadinessLevel;
  evidence_count: number;
  source_count: number;
  safe_url_count: number;
  reviewed_count: number;
  source_url_coverage: number;
  human_review_coverage: number;
  checks: Record<EvidenceReadinessCheck, boolean>;
  passed_checks: EvidenceReadinessCheck[];
  gaps: string[];
};

export type OpportunityReviewUpdate = {
  review_state: ReviewState;
  review_note: string | null;
};

export type EvidenceReviewCreate = {
  item_id: string;
  label: EvidenceReviewLabel;
  user_note: string | null;
};

export type LabelOut = {
  id: string;
  item_id: string;
  label: string;
  user_note: string | null;
  created_at: string;
};

export type EvaluationLabelCounts = Record<EvidenceReviewLabel, number>;

export type EvaluationSlice = {
  total_items: number;
  reviewed_items: number;
  review_coverage: number;
  label_counts: EvaluationLabelCounts;
  precision_on_reviewed_positives: number | null;
};

export type Evaluation = {
  total_reviewable_items: number;
  reviewed_items: number;
  review_coverage: number;
  label_counts: EvaluationLabelCounts;
  unrecognized_latest_labels: number;
  precision_on_reviewed_positives: number | null;
  by_source: Record<string, EvaluationSlice>;
  by_signal_type: Record<string, EvaluationSlice>;
  selection_bias_warning: string;
};
```

Extend existing types exactly:

```typescript
export type EvidenceItem = {
  id: string;
  source: string;
  url: string;
  title: string;
  body: string;
  signal_type: string;
  pain_score: number;
  task_concreteness_score: number;
  buying_intent_score: number;
  evidence_spans: string[];
  review_label: EvidenceReviewLabel | null;
  review_note: string | null;
  reviewed_at: string | null;
  review_history_count: number;
};

export type Opportunity = {
  id: string;
  cluster_id: string;
  title: string;
  problem_statement: string;
  target_user: string;
  current_workaround: string;
  suggested_mvp: string;
  why_now: string;
  feasibility_score: number;
  opportunity_score: number;
  competition_notes: string;
  scoring_breakdown_json: ScoreBreakdown;
  generated_prompt: string;
  review_state: ReviewState;
  review_note: string | null;
  decision_updated_at: string | null;
  created_at: string;
  updated_at: string;
  evidence_items: EvidenceItem[];
  signal_count: number;
  top_source: string;
  evidence_readiness: EvidenceReadiness;
};

export type TaskPack = {
  opportunity_id: string;
  title: string;
  problem: string;
  suggested_mvp: string;
  codex_prompt: string;
  markdown: string;
  evidence_urls: string[];
  acceptance_criteria: string[];
  privacy_constraints: string[];
  review_state: ReviewState;
  evidence_readiness: EvidenceReadiness;
};
```

Update the typed `opportunity` fixture in
`apps/web/tests/opportunity-detail.test.tsx`. Add to its evidence item:

```typescript
      review_label: null,
      review_note: null,
      reviewed_at: null,
      review_history_count: 0,
```

Add to the opportunity root:

```typescript
  review_state: "new",
  review_note: null,
  decision_updated_at: null,
  evidence_readiness: {
    level: "weak",
    evidence_count: 1,
    source_count: 1,
    safe_url_count: 1,
    reviewed_count: 0,
    source_url_coverage: 1,
    human_review_coverage: 0,
    checks: {
      enough_evidence: false,
      source_diversity: false,
      source_url_coverage: true,
      human_review_coverage: false,
    },
    passed_checks: ["source_url_coverage"],
    gaps: [
      "Collect 4 more evidence items.",
      "Add evidence from 1 more source.",
      "Review 1 more evidence item.",
    ],
  },
```

- [ ] **Step 4: Add ordered runtime metadata and one API error formatter**

Create `apps/web/src/lib/review.ts`:

```typescript
import type {
  EvidenceReadinessCheck,
  EvidenceReadinessLevel,
  EvidenceReviewLabel,
  ReviewState,
} from "./types";

type BadgeTone = "slate" | "green" | "amber" | "blue" | "red";

export const REVIEW_STATE_OPTIONS: {
  value: ReviewState;
  label: string;
  tone: BadgeTone;
}[] = [
  { value: "new", label: "New", tone: "slate" },
  { value: "needs_more_evidence", label: "Needs more evidence", tone: "amber" },
  { value: "promising", label: "Promising", tone: "blue" },
  { value: "rejected", label: "Rejected", tone: "red" },
  { value: "duplicate", label: "Duplicate", tone: "slate" },
  { value: "build_candidate", label: "Build candidate", tone: "green" },
];

export const EVIDENCE_REVIEW_OPTIONS: {
  value: EvidenceReviewLabel;
  label: string;
}[] = [
  { value: "true_signal", label: "True signal" },
  { value: "false_positive", label: "False positive" },
  { value: "unclear", label: "Unclear" },
  { value: "duplicate", label: "Duplicate" },
  { value: "not_actionable", label: "Not actionable" },
  { value: "sensitive_risk", label: "Sensitive risk" },
];

export const READINESS_CHECKS: { key: EvidenceReadinessCheck; label: string }[] = [
  { key: "enough_evidence", label: "Enough evidence" },
  { key: "source_diversity", label: "Source diversity" },
  { key: "source_url_coverage", label: "Safe source URL coverage" },
  { key: "human_review_coverage", label: "Human review coverage" },
];

export const READINESS_TONES: Record<EvidenceReadinessLevel, BadgeTone> = {
  weak: "red",
  medium: "amber",
  strong: "green",
};

export function reviewStateOption(state: ReviewState) {
  return REVIEW_STATE_OPTIONS.find((option) => option.value === state)!;
}

export function evidenceReviewLabel(label: EvidenceReviewLabel) {
  return EVIDENCE_REVIEW_OPTIONS.find((option) => option.value === label)!.label;
}

export function formatPercentage(value: number) {
  return `${Math.round(value * 100)}%`;
}
```

Create `apps/web/src/lib/api-error.ts`:

```typescript
export function apiErrorMessage(error: unknown): string {
  if (!(error instanceof Error)) return "The request failed.";
  try {
    const parsed = JSON.parse(error.message) as {
      detail?: string | { msg?: string }[] | unknown;
    };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      const messages = parsed.detail
        .map((entry) => (typeof entry?.msg === "string" ? entry.msg : ""))
        .filter(Boolean);
      if (messages.length) return messages.join(" ");
    }
    if (parsed.detail !== undefined) return JSON.stringify(parsed.detail);
  } catch {
    return error.message;
  }
  return error.message;
}
```

Replace the local `errorMessage` implementation in `opportunity-detail.tsx`
with an import of `apiErrorMessage` and use that name at every call site.

- [ ] **Step 5: Add the API helpers**

Import the new types in `api.ts` and replace/add these methods:

```typescript
  opportunities: (reviewState?: ReviewState) => {
    const query = reviewState
      ? `?${new URLSearchParams({ review_state: reviewState })}`
      : "";
    return request<Opportunity[]>(`/api/opportunities${query}`);
  },
  updateOpportunityReview: (id: string, payload: OpportunityReviewUpdate) =>
    request<Opportunity>(`/api/opportunities/${id}/review`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  createEvidenceReview: (payload: EvidenceReviewCreate) =>
    request<LabelOut>("/api/labels", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  itemReviewHistory: (itemId: string) =>
    request<LabelOut[]>(`/api/items/${itemId}/labels`),
  evaluation: () => request<Evaluation>("/api/evaluation"),
```

In `dashboard.tsx`, immediately change the query function to avoid React Query
passing its context object as a state value:

```typescript
  const opportunities = useQuery({
    queryKey: ["opportunities"],
    queryFn: () => api.opportunities(),
  });
```

- [ ] **Step 6: Add the shared Textarea primitive**

Import `TextareaHTMLAttributes` in `ui.tsx` and add after `Select`:

```typescript
export type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  error?: boolean;
  success?: boolean;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea({ className, error, success, ...props }, ref) {
    return (
      <textarea
        ref={ref}
        aria-invalid={error || undefined}
        data-state={error ? "error" : success ? "success" : undefined}
        className={clsx(
          fieldBase,
          "min-h-24 resize-y px-3 py-2",
          error && "border-danger-border focus-visible:outline-danger",
          success && !error && "border-success-border focus-visible:outline-success",
          className,
        )}
        {...props}
      />
    );
  },
);
```

- [ ] **Step 7: Run focused web tests, lint, and type-aware build**

Run:

```bash
PATH="/opt/homebrew/opt/node@20/bin:$PATH" \
  npm --prefix apps/web test -- --run tests/api.test.ts tests/opportunity-detail.test.tsx
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web run lint
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web run build
```

Expected: API and existing opportunity-detail tests pass, lint exits 0, and Next.js completes a production build.

- [ ] **Step 8: Commit the frontend foundation checkpoint**

```bash
git add \
  apps/web/src/lib/types.ts \
  apps/web/src/lib/review.ts \
  apps/web/src/lib/api-error.ts \
  apps/web/src/lib/api.ts \
  apps/web/src/components/ui.tsx \
  apps/web/src/features/opportunity-detail.tsx \
  apps/web/tests/api.test.ts \
  apps/web/tests/opportunity-detail.test.tsx
git commit -m "feat(web): add decision workbench contracts"
```

---

### Task 6: Add opportunity decision, readiness, and evidence-review controls

**Files:**
- Create: `apps/web/src/features/opportunity-decision-panel.tsx`
- Create: `apps/web/src/features/evidence-readiness-card.tsx`
- Create: `apps/web/src/features/evidence-review-control.tsx`
- Create: `apps/web/tests/opportunity-decision-panel.test.tsx`
- Create: `apps/web/tests/evidence-readiness-card.test.tsx`
- Create: `apps/web/tests/evidence-review-control.test.tsx`
- Modify: `apps/web/src/features/opportunity-detail.tsx:1-458`

**Interfaces:**
- Consumes: `api.updateOpportunityReview`, `api.createEvidenceReview`, review metadata, `Textarea`, and enriched `Opportunity`/`EvidenceItem`.
- Produces: three focused components and a detail page that persists decisions/reviews without optimistic state or frontend readiness calculations.

- [ ] **Step 1: Write failing component tests**

Create `apps/web/tests/opportunity-decision-panel.test.tsx`:

```typescript
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OpportunityDecisionPanel } from "../src/features/opportunity-decision-panel";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({
  api: { updateOpportunityReview: vi.fn() },
}));

describe("OpportunityDecisionPanel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("saves an exact decision payload then invalidates detail and list", async () => {
    vi.mocked(api.updateOpportunityReview).mockResolvedValue({} as never);
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        <OpportunityDecisionPanel
          opportunityId="opportunity-1"
          reviewState="new"
          reviewNote={null}
          decisionUpdatedAt={null}
        />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText("Decision state"), {
      target: { value: "promising" },
    });
    fireEvent.change(screen.getByLabelText("Local review note"), {
      target: { value: "Validate with maintainers." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save decision" }));

    await waitFor(() => {
      expect(api.updateOpportunityReview).toHaveBeenCalledWith("opportunity-1", {
        review_state: "promising",
        review_note: "Validate with maintainers.",
      });
      expect(invalidate).toHaveBeenCalledWith({
        queryKey: ["opportunity", "opportunity-1"],
      });
      expect(invalidate).toHaveBeenCalledWith({ queryKey: ["opportunities"] });
    });
    expect(await screen.findByText("Decision saved")).toBeInTheDocument();
  });

  it("keeps confirmed state and draft visible after a failed save", async () => {
    vi.mocked(api.updateOpportunityReview).mockRejectedValue(
      new Error(JSON.stringify({ detail: "Could not save decision." })),
    );
    const client = new QueryClient();
    render(
      <QueryClientProvider client={client}>
        <OpportunityDecisionPanel
          opportunityId="opportunity-1"
          reviewState="new"
          reviewNote={null}
          decisionUpdatedAt={null}
        />
      </QueryClientProvider>,
    );
    fireEvent.change(screen.getByLabelText("Local review note"), {
      target: { value: "Keep this draft" },
    });
    expect(screen.getByLabelText("Local review note")).toHaveAttribute(
      "maxlength",
      "1000",
    );
    fireEvent.click(screen.getByRole("button", { name: "Save decision" }));

    expect(await screen.findByText("Could not save decision.")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Keep this draft")).toBeInTheDocument();
    expect(screen.getByText("Confirmed: New")).toBeInTheDocument();
    expect(screen.queryByText("Decision saved")).not.toBeInTheDocument();
  });
});
```

Create `apps/web/tests/evidence-readiness-card.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EvidenceReadinessCard } from "../src/features/evidence-readiness-card";

describe("EvidenceReadinessCard", () => {
  it("renders backend checks and a sensitive-risk gap without confidence copy", () => {
    render(
      <EvidenceReadinessCard
        readiness={{
          level: "weak",
          evidence_count: 5,
          source_count: 2,
          safe_url_count: 4,
          reviewed_count: 3,
          source_url_coverage: 0.8,
          human_review_coverage: 0.6,
          checks: {
            enough_evidence: true,
            source_diversity: true,
            source_url_coverage: true,
            human_review_coverage: true,
          },
          passed_checks: [
            "enough_evidence",
            "source_diversity",
            "source_url_coverage",
            "human_review_coverage",
          ],
          gaps: [
            "Resolve or exclude evidence marked sensitive risk before advancing.",
          ],
        }}
      />,
    );

    expect(screen.getByText("Evidence readiness")).toBeInTheDocument();
    expect(screen.getByText("Safe source URL coverage")).toBeInTheDocument();
    expect(screen.getByText(/sensitive risk/)).toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
  });
});
```

Create `apps/web/tests/evidence-review-control.test.tsx`:

```typescript
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EvidenceReviewControl } from "../src/features/evidence-review-control";
import { api } from "../src/lib/api";
import type { EvidenceItem } from "../src/lib/types";

vi.mock("../src/lib/api", () => ({
  api: { createEvidenceReview: vi.fn() },
}));

const item: EvidenceItem = {
  id: "item-1",
  source: "hackernews",
  url: "https://news.ycombinator.com/item?id=1",
  title: "AI code review",
  body: "We need production-readiness checks for AI-generated code.",
  signal_type: "pain",
  pain_score: 0.9,
  task_concreteness_score: 0.8,
  buying_intent_score: 0.4,
  evidence_spans: ["need production-readiness checks"],
  review_label: null,
  review_note: null,
  reviewed_at: null,
  review_history_count: 0,
};

describe("EvidenceReviewControl", () => {
  beforeEach(() => vi.clearAllMocks());

  it("appends a review and invalidates every dependent query", async () => {
    vi.mocked(api.createEvidenceReview).mockResolvedValue({} as never);
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(
      <QueryClientProvider client={client}>
        <EvidenceReviewControl opportunityId="opportunity-1" item={item} />
      </QueryClientProvider>,
    );

    fireEvent.change(screen.getByLabelText("Evidence label"), {
      target: { value: "true_signal" },
    });
    fireEvent.change(screen.getByLabelText("New evidence review note"), {
      target: { value: "Useful signal." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add evidence review" }));

    await waitFor(() => {
      expect(api.createEvidenceReview).toHaveBeenCalledWith({
        item_id: "item-1",
        label: "true_signal",
        user_note: "Useful signal.",
      });
      for (const queryKey of [
        ["opportunity", "opportunity-1"],
        ["opportunities"],
        ["evaluation"],
        ["item-labels", "item-1"],
      ]) {
        expect(invalidate).toHaveBeenCalledWith({ queryKey });
      }
    });
    expect(screen.getByLabelText("New evidence review note")).toHaveAttribute(
      "maxlength",
      "500",
    );
    expect(screen.getByLabelText("New evidence review note")).toHaveValue("");
  });
});
```

- [ ] **Step 2: Run the three tests and confirm the components are missing**

Run:

```bash
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web test -- --run \
  tests/opportunity-decision-panel.test.tsx \
  tests/evidence-readiness-card.test.tsx \
  tests/evidence-review-control.test.tsx
```

Expected: FAIL at import resolution because the three components do not exist.

- [ ] **Step 3: Implement the opportunity decision panel**

Create `apps/web/src/features/opportunity-decision-panel.tsx`:

```typescript
"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-error";
import { REVIEW_STATE_OPTIONS, reviewStateOption } from "@/lib/review";
import type { ReviewState } from "@/lib/types";
import { Badge, Button, Card, Select, StateMessage, Textarea } from "@/components/ui";

export function OpportunityDecisionPanel({
  opportunityId,
  reviewState,
  reviewNote,
  decisionUpdatedAt,
}: {
  opportunityId: string;
  reviewState: ReviewState;
  reviewNote: string | null;
  decisionUpdatedAt: string | null;
}) {
  const queryClient = useQueryClient();
  const [draftState, setDraftState] = useState<ReviewState>(reviewState);
  const [draftNote, setDraftNote] = useState(reviewNote ?? "");
  const mutation = useMutation({
    mutationFn: () =>
      api.updateOpportunityReview(opportunityId, {
        review_state: draftState,
        review_note: draftNote.trim() || null,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["opportunity", opportunityId] }),
        queryClient.invalidateQueries({ queryKey: ["opportunities"] }),
      ]);
    },
  });
  const confirmed = reviewStateOption(reviewState);

  return (
    <Card className="space-y-4" aria-label="Opportunity decision">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Decision</h2>
          <p className="mt-1 text-sm leading-6 text-muted">
            Only the local operator can promote an opportunity to a build candidate.
          </p>
        </div>
        <Badge tone={confirmed.tone}>Confirmed: {confirmed.label}</Badge>
      </div>
      <label className="block">
        <span className="text-sm font-semibold text-muted">Decision state</span>
        <Select
          className="mt-2"
          value={draftState}
          onChange={(event) => setDraftState(event.target.value as ReviewState)}
        >
          {REVIEW_STATE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </Select>
      </label>
      <label className="block">
        <span className="text-sm font-semibold text-muted">Local review note</span>
        <Textarea
          className="mt-2"
          maxLength={1000}
          value={draftNote}
          onChange={(event) => setDraftNote(event.target.value)}
        />
        <span className="mt-1 flex justify-between text-xs text-muted">
          <span>Excluded from exports.</span><span>{draftNote.length}/1000</span>
        </span>
      </label>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">
          {decisionUpdatedAt ? (
            <>Last decision update: <time dateTime={decisionUpdatedAt}>{new Date(decisionUpdatedAt).toLocaleString()}</time></>
          ) : "No decision saved yet."}
        </p>
        <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>
          Save decision
        </Button>
      </div>
      {mutation.error ? (
        <StateMessage tone="danger" title="Decision was not saved">
          {apiErrorMessage(mutation.error)}
        </StateMessage>
      ) : null}
      {mutation.isSuccess ? (
        <StateMessage tone="success" title="Decision saved" />
      ) : null}
    </Card>
  );
}
```

- [ ] **Step 4: Implement the readiness and evidence-review components**

Create `apps/web/src/features/evidence-readiness-card.tsx`:

```typescript
import { Badge, Card } from "@/components/ui";
import { formatPercentage, READINESS_CHECKS, READINESS_TONES } from "@/lib/review";
import type { EvidenceReadiness } from "@/lib/types";

export function EvidenceReadinessCard({ readiness }: { readiness: EvidenceReadiness }) {
  return (
    <Card variant="muted">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Evidence readiness</h2>
          <p className="mt-1 text-sm text-muted">Review preparation, not market validation.</p>
        </div>
        <Badge tone={READINESS_TONES[readiness.level]}>{readiness.level}</Badge>
      </div>
      <p className="mt-3 text-sm text-muted">
        {readiness.evidence_count} evidence · {readiness.source_count} sources · {readiness.safe_url_count} safe URLs · {readiness.reviewed_count} reviewed
      </p>
      <p className="mt-1 text-xs text-muted">
        URL coverage {formatPercentage(readiness.source_url_coverage)} · Human review {formatPercentage(readiness.human_review_coverage)}
      </p>
      <ul className="mt-4 grid gap-2 text-sm">
        {READINESS_CHECKS.map(({ key, label }) => (
          <li key={key} className="flex justify-between gap-3">
            <span>{label}</span><span>{readiness.checks[key] ? "Passed" : "Needs work"}</span>
          </li>
        ))}
      </ul>
      {readiness.gaps.length ? (
        <ul className="mt-4 list-disc space-y-1 pl-5 text-sm text-muted">
          {readiness.gaps.map((gap) => <li key={gap}>{gap}</li>)}
        </ul>
      ) : null}
    </Card>
  );
}
```

Create `apps/web/src/features/evidence-review-control.tsx`:

```typescript
"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-error";
import { EVIDENCE_REVIEW_OPTIONS, evidenceReviewLabel } from "@/lib/review";
import type { EvidenceItem, EvidenceReviewLabel } from "@/lib/types";
import { Badge, Button, Select, StateMessage, Textarea } from "@/components/ui";

export function EvidenceReviewControl({ opportunityId, item }: {
  opportunityId: string;
  item: EvidenceItem;
}) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState<EvidenceReviewLabel>("true_signal");
  const [note, setNote] = useState("");
  const mutation = useMutation({
    mutationFn: () => api.createEvidenceReview({
      item_id: item.id,
      label,
      user_note: note.trim() || null,
    }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["opportunity", opportunityId] }),
        queryClient.invalidateQueries({ queryKey: ["opportunities"] }),
        queryClient.invalidateQueries({ queryKey: ["evaluation"] }),
        queryClient.invalidateQueries({ queryKey: ["item-labels", item.id] }),
      ]);
      setNote("");
    },
  });

  return (
    <div className="mt-4 border-t border-border pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-ink">Evidence review</span>
        {item.review_label ? <Badge>{evidenceReviewLabel(item.review_label)}</Badge> : null}
        {!item.review_label && item.review_history_count > 0 ? <Badge>No current recognized label</Badge> : null}
        <span className="text-xs text-muted">{item.review_history_count} stored review(s)</span>
      </div>
      {item.review_note ? <p className="mt-2 text-sm text-muted">Current note: {item.review_note}</p> : null}
      {item.reviewed_at ? <time className="mt-1 block text-xs text-muted" dateTime={item.reviewed_at}>{new Date(item.reviewed_at).toLocaleString()}</time> : null}
      <div className="mt-3 grid gap-3 md:grid-cols-[220px_minmax(0,1fr)_auto] md:items-end">
        <label><span className="text-xs font-semibold text-muted">Evidence label</span><Select className="mt-1" value={label} onChange={(event) => setLabel(event.target.value as EvidenceReviewLabel)}>{EVIDENCE_REVIEW_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</Select></label>
        <label><span className="text-xs font-semibold text-muted">New evidence review note</span><Textarea className="mt-1 min-h-20" maxLength={500} value={note} onChange={(event) => setNote(event.target.value)} /></label>
        <Button onClick={() => mutation.mutate()} loading={mutation.isPending}>Add evidence review</Button>
      </div>
      <p className="mt-2 text-xs text-muted">Saving adds a review; it does not edit prior history. Notes stay out of exports.</p>
      {mutation.error ? <StateMessage className="mt-3" tone="danger" title="Evidence review was not saved">{apiErrorMessage(mutation.error)}</StateMessage> : null}
      {mutation.isSuccess ? <StateMessage className="mt-3" tone="success" title="Evidence review added" /> : null}
    </div>
  );
}
```

- [ ] **Step 5: Integrate the focused components into opportunity detail**

Import the three components. Immediately after the title/score grid add:

```typescript
      <OpportunityDecisionPanel
        key={`${data.id}:${data.decision_updated_at ?? "unsaved"}`}
        opportunityId={data.id}
        reviewState={data.review_state}
        reviewNote={data.review_note}
        decisionUpdatedAt={data.decision_updated_at}
      />
```

Replace the local `sourcesWithUrls` calculation and the current evidence-trail
summary card with:

```typescript
      <div className="grid gap-4 lg:grid-cols-2">
        <EvidenceReadinessCard readiness={data.evidence_readiness} />
        <Card variant="muted">
          <h2 className="text-lg font-semibold text-ink">Evidence trail</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone="blue">{data.signal_count} signals</Badge>
            {sourceMixLabel ? <Badge>Source mix: {sourceMixLabel}</Badge> : <Badge>No source mix yet</Badge>}
            <Badge tone="green">{data.evidence_readiness.safe_url_count}/{data.evidence_items.length} with safe source URLs</Badge>
          </div>
          <p className="mt-3 text-sm leading-6 text-muted">Evidence excerpts come from detector spans. Author identity is omitted from exports; safe source URLs are preserved for review.</p>
        </Card>
      </div>
```

Inside each evidence item article, after its existing evidence/source content and
before the closing article tag, add:

```typescript
                <EvidenceReviewControl opportunityId={data.id} item={item} />
```

- [ ] **Step 6: Run focused and integration tests**

Run:

```bash
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web test -- --run \
  tests/opportunity-decision-panel.test.tsx \
  tests/evidence-readiness-card.test.tsx \
  tests/evidence-review-control.test.tsx \
  tests/opportunity-detail.test.tsx
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web run lint
```

Expected: all focused/detail tests pass, existing prompt-enhancement behavior stays green, and lint exits 0.

- [ ] **Step 7: Commit the opportunity-review UI checkpoint**

```bash
git add \
  apps/web/src/features/opportunity-decision-panel.tsx \
  apps/web/src/features/evidence-readiness-card.tsx \
  apps/web/src/features/evidence-review-control.tsx \
  apps/web/src/features/opportunity-detail.tsx \
  apps/web/tests/opportunity-decision-panel.test.tsx \
  apps/web/tests/evidence-readiness-card.test.tsx \
  apps/web/tests/evidence-review-control.test.tsx \
  apps/web/tests/opportunity-detail.test.tsx
git commit -m "feat(web): add opportunity review controls"
```

---

### Task 7: Turn the dashboard into a decision queue and add Evaluation

**Files:**
- Create: `apps/web/src/features/evaluation.tsx`
- Create: `apps/web/src/app/evaluation/page.tsx`
- Create: `apps/web/tests/evaluation.test.tsx`
- Create: `apps/web/tests/app-shell.test.tsx`
- Modify: `apps/web/src/features/dashboard.tsx:57-605`
- Modify: `apps/web/src/components/app-shell.tsx:7-38,135-146`
- Modify: `apps/web/tests/dashboard.test.tsx:1-89`

**Interfaces:**
- Consumes: full unfiltered `api.opportunities()` response, review metadata, `api.evaluation()`, and backend-owned evaluation slices.
- Produces: instant local state filtering/counts, Decision/Readiness table columns, `/evaluation`, and active Evaluation navigation.

- [ ] **Step 1: Write failing dashboard and Evaluation tests**

Add this fixture/helper and test to `apps/web/tests/dashboard.test.tsx`:

```typescript
const readiness = {
  level: "medium" as const,
  evidence_count: 5,
  source_count: 2,
  safe_url_count: 4,
  reviewed_count: 2,
  source_url_coverage: 0.8,
  human_review_coverage: 0.4,
  checks: {
    enough_evidence: true,
    source_diversity: true,
    source_url_coverage: true,
    human_review_coverage: false,
  },
  passed_checks: [
    "enough_evidence" as const,
    "source_diversity" as const,
    "source_url_coverage" as const,
  ],
  gaps: ["Review 1 more evidence item."],
};

function opportunity(id: string, title: string, reviewState: ReviewState): Opportunity {
  return {
    id,
    cluster_id: `cluster-${id}`,
    title,
    problem_statement: "Repeated workflow pain.",
    target_user: "Maintainers",
    current_workaround: "Manual work",
    suggested_mvp: "Focused local tool",
    why_now: "Repeated evidence",
    feasibility_score: 0.8,
    opportunity_score: 0.7,
    competition_notes: "Narrow scope",
    scoring_breakdown_json: {},
    generated_prompt: "# Build",
    review_state: reviewState,
    review_note: null,
    decision_updated_at: null,
    evidence_readiness: readiness,
    created_at: "2026-07-09T10:00:00Z",
    updated_at: "2026-07-09T10:00:00Z",
    evidence_items: [],
    signal_count: 5,
    top_source: "github",
  };
}

it("filters the decision queue locally without another API call", async () => {
  vi.mocked(api.opportunities).mockResolvedValue([
    opportunity("1", "New idea", "new"),
    opportunity("2", "Promising idea", "promising"),
    opportunity("3", "Rejected idea", "rejected"),
  ]);
  renderWithClient(<Dashboard />);

  expect(await screen.findByText("Promising idea")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Promising 1" }));

  expect(screen.getByText("Promising idea")).toBeInTheDocument();
  expect(screen.queryByText("New idea")).not.toBeInTheDocument();
  expect(screen.queryByText("Rejected idea")).not.toBeInTheDocument();
  expect(api.opportunities).toHaveBeenCalledTimes(1);
  expect(screen.getByText("Promising")).toBeInTheDocument();
  expect(screen.getByText("medium")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "Build candidate 0" }));
  expect(screen.getByText("No opportunities match this decision state")).toBeInTheDocument();
  expect(screen.queryByText("No ranked opportunities yet")).not.toBeInTheDocument();
});
```

Import `fireEvent`, `Opportunity`, and `ReviewState` in that test file.

Create `apps/web/tests/evaluation.test.tsx`:

```typescript
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Evaluation } from "../src/features/evaluation";
import { api } from "../src/lib/api";

vi.mock("../src/lib/api", () => ({ api: { evaluation: vi.fn() } }));

function renderEvaluation() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><Evaluation /></QueryClientProvider>);
}

const zeroCounts = {
  true_signal: 0,
  false_positive: 0,
  unclear: 0,
  duplicate: 0,
  not_actionable: 0,
  sensitive_risk: 0,
};

describe("Evaluation", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders reviewed precision including a valid zero", async () => {
    vi.mocked(api.evaluation).mockResolvedValue({
      total_reviewable_items: 4,
      reviewed_items: 1,
      review_coverage: 0.25,
      label_counts: { ...zeroCounts, false_positive: 1 },
      unrecognized_latest_labels: 0,
      precision_on_reviewed_positives: 0,
      by_source: {
        github: {
          total_items: 4,
          reviewed_items: 1,
          review_coverage: 0.25,
          label_counts: { ...zeroCounts, false_positive: 1 },
          precision_on_reviewed_positives: 0,
        },
      },
      by_signal_type: {},
      selection_bias_warning: "Metrics describe only manually reviewed evidence and may not represent all detected items.",
    });
    renderEvaluation();

    expect(await screen.findByText("Evidence evaluation")).toBeInTheDocument();
    const precisionTile = screen.getByText("Reviewed precision").closest("section");
    expect(precisionTile).not.toBeNull();
    expect(within(precisionTile!).getByText("0%")).toBeInTheDocument();
    expect(screen.getByText(/may not represent all detected items/)).toBeInTheDocument();
    expect(screen.getByText(/Recall and F1 are not reported/)).toBeInTheDocument();
    expect(screen.queryByText("Not defined")).not.toBeInTheDocument();
  });

  it("separates no evidence from evidence with no reviews", async () => {
    vi.mocked(api.evaluation).mockResolvedValue({
      total_reviewable_items: 0,
      reviewed_items: 0,
      review_coverage: 0,
      label_counts: zeroCounts,
      unrecognized_latest_labels: 0,
      precision_on_reviewed_positives: null,
      by_source: {},
      by_signal_type: {},
      selection_bias_warning: "Metrics describe only manually reviewed evidence and may not represent all detected items.",
    });
    const view = renderEvaluation();
    expect(await screen.findByText("No reviewable evidence yet")).toBeInTheDocument();
    expect(screen.getByText(/Recall and F1 are not reported/)).toBeInTheDocument();
    view.unmount();

    vi.mocked(api.evaluation).mockResolvedValue({
      total_reviewable_items: 4,
      reviewed_items: 0,
      review_coverage: 0,
      label_counts: zeroCounts,
      unrecognized_latest_labels: 0,
      precision_on_reviewed_positives: null,
      by_source: {},
      by_signal_type: {},
      selection_bias_warning: "Metrics describe only manually reviewed evidence and may not represent all detected items.",
    });
    renderEvaluation();
    expect(await screen.findByText("Evidence is ready for review")).toBeInTheDocument();
    expect(screen.getByText("Not defined")).toBeInTheDocument();
  });

  it("renders backend error details", async () => {
    vi.mocked(api.evaluation).mockRejectedValue(
      new Error(JSON.stringify({ detail: "Evaluation is unavailable." })),
    );
    renderEvaluation();

    expect(
      await screen.findByText("Could not load evidence evaluation"),
    ).toBeInTheDocument();
    expect(screen.getByText("Evaluation is unavailable.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the focused tests and confirm queue/Evaluation behavior is absent**

Run:

```bash
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web test -- --run \
  tests/dashboard.test.tsx tests/evaluation.test.tsx
```

Expected: FAIL because dashboard filters and the Evaluation feature do not exist.

- [ ] **Step 3: Implement local dashboard counts and filtering**

Import `REVIEW_STATE_OPTIONS`, `READINESS_TONES`, `reviewStateOption`, and
`ReviewState`. Add only this state beside the existing `useState` calls:

```typescript
  const [reviewStateFilter, setReviewStateFilter] = useState<ReviewState | "all">("all");
```

After the `stats`, `opportunities`, `readiness`, and `scans` `useQuery`
declarations, replace the old `topOpportunity` and `hasOpportunities`
declarations with:

```typescript
  const allOpportunities = opportunities.data ?? [];
  const decisionCounts = Object.fromEntries(
    REVIEW_STATE_OPTIONS.map((option) => [
      option.value,
      allOpportunities.filter((item) => item.review_state === option.value).length,
    ]),
  ) as Record<ReviewState, number>;
  const filteredOpportunities = reviewStateFilter === "all"
    ? allOpportunities
    : allOpportunities.filter((item) => item.review_state === reviewStateFilter);
  const topOpportunity = allOpportunities[0];
  const hasOpportunities = allOpportunities.length > 0;
  const hasFilteredOpportunities = filteredOpportunities.length > 0;
```

Before the table, render these accessible local filters:

```typescript
          <div className="mb-4 flex flex-wrap gap-2" aria-label="Decision state filter">
            <Button size="sm" variant={reviewStateFilter === "all" ? "primary" : "secondary"} aria-pressed={reviewStateFilter === "all"} onClick={() => setReviewStateFilter("all")}>All {allOpportunities.length}</Button>
            {REVIEW_STATE_OPTIONS.map((option) => (
              <Button key={option.value} size="sm" variant={reviewStateFilter === option.value ? "primary" : "secondary"} aria-pressed={reviewStateFilter === option.value} onClick={() => setReviewStateFilter(option.value)}>
                {option.label} {decisionCounts[option.value]}
              </Button>
            ))}
          </div>
```

Add `Decision` and `Readiness` headers, change the table minimum width to
`min-w-[980px]`, change every loading/global-empty `colSpan` from 7 to 9, and
render `filteredOpportunities`. For each row add:

```typescript
                    <td className="py-3 pr-4">
                      <Badge tone={reviewStateOption(opportunity.review_state).tone}>
                        {reviewStateOption(opportunity.review_state).label}
                      </Badge>
                    </td>
                    <td className="py-3 pr-4">
                      <Badge tone={READINESS_TONES[opportunity.evidence_readiness.level]}>
                        {opportunity.evidence_readiness.level}
                      </Badge>
                    </td>
```

When `hasOpportunities` is true but `hasFilteredOpportunities` is false, render
one nine-column row containing exactly `No opportunities match this decision
state`. Keep the current `No ranked opportunities yet` row only for a globally
empty list.

- [ ] **Step 4: Implement the Evaluation feature and route**

Create `apps/web/src/features/evaluation.tsx`:

```typescript
"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/api-error";
import { EVIDENCE_REVIEW_OPTIONS, formatPercentage } from "@/lib/review";
import type { EvaluationSlice } from "@/lib/types";
import { Card, EmptyState, MetricTile, PageHeader, StateMessage, TableShell } from "@/components/ui";

function BreakdownTable({ title, rows }: { title: string; rows: Record<string, EvaluationSlice> }) {
  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <TableShell className="mt-4" tableClassName="min-w-[560px]">
        <thead><tr className="border-b border-border text-xs uppercase text-muted"><th className="py-2 pr-3">Group</th><th className="py-2 pr-3">Total</th><th className="py-2 pr-3">Reviewed</th><th className="py-2 pr-3">Coverage</th><th className="py-2">Precision</th></tr></thead>
        <tbody>{Object.entries(rows).map(([name, row]) => <tr key={name} className="border-b border-border last:border-0"><td className="py-3 pr-3 font-medium">{name}</td><td className="py-3 pr-3">{row.total_items}</td><td className="py-3 pr-3">{row.reviewed_items}</td><td className="py-3 pr-3">{formatPercentage(row.review_coverage)}</td><td className="py-3">{row.precision_on_reviewed_positives === null ? "Not defined" : formatPercentage(row.precision_on_reviewed_positives)}</td></tr>)}</tbody>
      </TableShell>
    </Card>
  );
}

export function Evaluation() {
  const query = useQuery({ queryKey: ["evaluation"], queryFn: api.evaluation });
  if (query.isLoading) return <StateMessage tone="info" title="Loading evidence evaluation" />;
  if (query.error) return <StateMessage tone="danger" title="Could not load evidence evaluation">{apiErrorMessage(query.error)}</StateMessage>;
  const data = query.data;
  if (!data) return <StateMessage tone="danger" title="Evaluation response was empty" />;
  const limits = (
    <StateMessage tone="warning" title="Evaluation limits">
      {data.selection_bias_warning} Recall and F1 are not reported because TaskSignal has no reviewed negative population.
    </StateMessage>
  );
  if (data.total_reviewable_items === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="Evidence evaluation" description="Selection-biased human review metrics for linked opportunity evidence." />
        <EmptyState title="No reviewable evidence yet" description="Process fixture or live data to generate opportunities and linked evidence." />
        {limits}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Evidence evaluation" description="Selection-biased human review metrics for linked opportunity evidence." />
      {data.reviewed_items === 0 ? <StateMessage tone="info" title="Evidence is ready for review">Open an opportunity and label its evidence to populate this report.</StateMessage> : null}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <MetricTile label="Reviewable" value={data.total_reviewable_items} />
        <MetricTile label="Reviewed" value={data.reviewed_items} />
        <MetricTile label="Coverage" value={formatPercentage(data.review_coverage)} />
        <MetricTile label="Reviewed precision" value={data.precision_on_reviewed_positives === null ? "Not defined" : formatPercentage(data.precision_on_reviewed_positives)} />
        <MetricTile label="Legacy latest labels" value={data.unrecognized_latest_labels} />
      </div>
      <Card><h2 className="text-lg font-semibold text-ink">Label counts</h2><dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{EVIDENCE_REVIEW_OPTIONS.map((option) => <div key={option.value}><dt className="text-sm text-muted">{option.label}</dt><dd className="text-2xl font-semibold text-ink">{data.label_counts[option.value]}</dd></div>)}</dl></Card>
      <div className="grid gap-4 xl:grid-cols-2"><BreakdownTable title="By source" rows={data.by_source} /><BreakdownTable title="By signal type" rows={data.by_signal_type} /></div>
      {limits}
    </div>
  );
}
```

Create `apps/web/src/app/evaluation/page.tsx`:

```typescript
import { AppShell } from "@/components/app-shell";
import { Evaluation } from "@/features/evaluation";

export default function EvaluationPage() {
  return <AppShell><Evaluation /></AppShell>;
}
```

- [ ] **Step 5: Add Evaluation navigation and its active-state test**

Import `ClipboardCheck` in `app-shell.tsx`, add this nav item after Dashboard,
and change the mobile grid from three to four columns:

```typescript
  { href: "/evaluation", label: "Evaluation", icon: ClipboardCheck },
```

Create `apps/web/tests/app-shell.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell } from "../src/components/app-shell";

vi.mock("next/navigation", () => ({ usePathname: () => "/evaluation" }));

describe("AppShell", () => {
  it("marks Evaluation as the active navigation destination", () => {
    render(<AppShell><p>Content</p></AppShell>);
    for (const link of screen.getAllByRole("link", { name: "Evaluation" })) {
      expect(link).toHaveAttribute("href", "/evaluation");
      expect(link).toHaveAttribute("aria-current", "page");
    }
  });
});
```

- [ ] **Step 6: Run dashboard/Evaluation tests and full frontend checks**

Run:

```bash
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web test -- --run \
  tests/dashboard.test.tsx tests/evaluation.test.tsx tests/app-shell.test.tsx
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web test
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web run lint
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web run build
```

Expected: focused tests and the complete frontend suite pass, lint exits 0, and the production build includes `/evaluation`.

- [ ] **Step 7: Commit the decision-queue/Evaluation checkpoint**

```bash
git add \
  apps/web/src/features/dashboard.tsx \
  apps/web/src/features/evaluation.tsx \
  apps/web/src/app/evaluation/page.tsx \
  apps/web/src/components/app-shell.tsx \
  apps/web/tests/dashboard.test.tsx \
  apps/web/tests/evaluation.test.tsx \
  apps/web/tests/app-shell.test.tsx
git commit -m "feat(web): add decision queue and evaluation"
```

---

### Task 8: Extend the credential-free smoke proof through the decision loop

**Files:**
- Modify: `scripts/first_run_smoke.py:270-434,637-721,807-818`
- Modify: `apps/api/tests/test_first_run_smoke.py:20-58,270-520`

**Interfaces:**
- Consumes: Tasks 3-4 review/evaluation/export endpoints and the eight-section task-pack contract.
- Produces: proof output that demonstrates persisted `promising` state, one evidence review, changed evaluation, decision-aware exports, and local-note exclusion.

- [ ] **Step 1: Write failing proof-summary/report tests**

Add these fields to `smoke_result()` in `test_first_run_smoke.py`:

```python
        "decision_review_state": "promising",
        "evidence_reviews": 1,
        "evaluation_reviewed_items_before": 0,
        "evaluation_reviewed_items": 1,
        "evaluation_review_coverage_before": 0.0,
        "evaluation_review_coverage": 0.2,
        "task_pack_readiness": "medium",
```

Keep `task_pack_required_sections` at `8` from Task 4. Add:

```python
def test_proof_summary_records_decision_review_workflow() -> None:
    summary = smoke_summary()

    check = summary["checks"]["decision_review_workflow"]
    assert check["result"] == "passed"
    assert check["evidence"] == {
        "review_state": "promising",
        "evidence_reviews": 1,
        "reviewed_items_before": 0,
        "reviewed_items": 1,
        "review_coverage_before": 0.0,
        "review_coverage": 0.2,
        "task_pack_readiness": "medium",
        "local_notes_exported": False,
    }


def test_proof_report_mentions_decision_workflow_without_local_notes() -> None:
    report = first_run_smoke.proof_report_markdown(
        smoke_result(),
        dashboard_source_checked=True,
        live_dashboard_checked=None,
        revision="codex/first-run-proof-report @ abc123 (clean)",
        generated_at=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
    )

    assert "Decision review workflow | passed" in report
    assert "state=promising" in report
    assert "1 reviewed evidence item" in report
    assert "reviewed items=0->1" in report
    assert "local notes excluded" in report
```

- [ ] **Step 2: Run focused smoke tests and confirm the proof fields are absent**

Run:

```bash
apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_first_run_smoke.py::test_proof_summary_records_decision_review_workflow \
  apps/api/tests/test_first_run_smoke.py::test_proof_report_mentions_decision_workflow_without_local_notes \
  -v
```

Expected: FAIL because `decision_review_workflow` is not in the summary/report.

- [ ] **Step 3: Exercise decisions, evidence review, evaluation, and note exclusion in `run_api_checks`**

In `run_api_checks`, after selecting `first_opportunity` and before fetching the
task pack, add this exact flow:

```python
        evidence_items = first_opportunity.get("evidence_items")
        assert_condition(
            isinstance(evidence_items, list) and evidence_items,
            "Top opportunity has no reviewable evidence.",
        )
        evidence_item = evidence_items[0]
        assert_condition(
            isinstance(evidence_item, dict) and evidence_item.get("id"),
            "Top evidence item is missing an id.",
        )
        opportunity_note = "SMOKE-LOCAL-OPPORTUNITY-NOTE-EXCLUDE"
        evidence_note = "SMOKE-LOCAL-EVIDENCE-NOTE-EXCLUDE"
        reviewed_opportunity = client_json(
            client,
            "PATCH",
            f"/api/opportunities/{first_opportunity['id']}/review",
            {"review_state": "promising", "review_note": opportunity_note},
        )
        baseline_evaluation = client_json(client, "GET", "/api/evaluation")
        evidence_review = client_json(
            client,
            "POST",
            "/api/labels",
            {
                "item_id": evidence_item["id"],
                "label": "true_signal",
                "user_note": evidence_note,
            },
        )
        evaluation = client_json(client, "GET", "/api/evaluation")
        assert_condition(
            isinstance(reviewed_opportunity, dict)
            and reviewed_opportunity.get("review_state") == "promising",
            "Opportunity decision did not persist.",
        )
        assert_condition(
            isinstance(evidence_review, dict)
            and evidence_review.get("label") == "true_signal",
            "Evidence review did not persist.",
        )
        assert_condition(
            isinstance(baseline_evaluation, dict)
            and isinstance(evaluation, dict)
            and evaluation.get("reviewed_items", 0)
            > baseline_evaluation.get("reviewed_items", 0)
            and evaluation.get("review_coverage", 0.0)
            > baseline_evaluation.get("review_coverage", 0.0),
            "Evaluation did not increase after the evidence review.",
        )
```

After fetching `task_pack`, fetch the evidence Markdown and assert the contract:

```python
        evidence_response = client.get(
            f"/api/opportunities/{first_opportunity['id']}/evidence.md"
        )
        assert_condition(
            evidence_response.status_code == 200,
            "Evidence Markdown export failed.",
        )
        export_text = json.dumps(task_pack, sort_keys=True) + evidence_response.text
        assert_condition(
            task_pack.get("review_state") == "promising",
            "Task pack is missing the decision state.",
        )
        readiness = task_pack.get("evidence_readiness")
        assert_condition(
            isinstance(readiness, dict)
            and readiness.get("level") in {"weak", "medium", "strong"},
            "Task pack is missing evidence readiness.",
        )
        assert_condition(
            "## Decision Context" in str(task_pack.get("markdown", "")),
            "Task pack is missing Decision Context.",
        )
        assert_condition(
            opportunity_note not in export_text and evidence_note not in export_text,
            "Local review notes leaked into an export.",
        )
```

Add these returned fields:

```python
            "decision_review_state": reviewed_opportunity["review_state"],
            "evidence_reviews": 1,
            "evaluation_reviewed_items_before": baseline_evaluation[
                "reviewed_items"
            ],
            "evaluation_reviewed_items": evaluation["reviewed_items"],
            "evaluation_review_coverage_before": baseline_evaluation[
                "review_coverage"
            ],
            "evaluation_review_coverage": evaluation["review_coverage"],
            "task_pack_readiness": readiness["level"],
```

- [ ] **Step 4: Add the machine-readable and Markdown proof rows**

Add to `proof_summary()["checks"]`:

```python
            "decision_review_workflow": {
                "result": "passed",
                "evidence": {
                    "review_state": result["decision_review_state"],
                    "evidence_reviews": result["evidence_reviews"],
                    "reviewed_items_before": result[
                        "evaluation_reviewed_items_before"
                    ],
                    "reviewed_items": result["evaluation_reviewed_items"],
                    "review_coverage_before": result[
                        "evaluation_review_coverage_before"
                    ],
                    "review_coverage": result["evaluation_review_coverage"],
                    "task_pack_readiness": result["task_pack_readiness"],
                    "local_notes_exported": False,
                },
            },
```

Add this report row after Task-pack structure:

```python
        (
            "| Decision review workflow | passed | "
            f"state={result['decision_review_state']}, "
            f"{result['evidence_reviews']} reviewed evidence item, "
            f"reviewed items={result['evaluation_reviewed_items_before']}"
            f"->{result['evaluation_reviewed_items']}, "
            f"coverage={result['evaluation_review_coverage_before']:.0%}"
            f"->{result['evaluation_review_coverage']:.0%}, "
            f"readiness={result['task_pack_readiness']}, local notes excluded |"
        ),
```

Print one additional successful CLI line in `main()`:

```python
        print(
            "[OK] Decision workflow: "
            f"{result['decision_review_state']}, "
            f"{result['evidence_reviews']} evidence review, "
            "local notes excluded",
            flush=True,
        )
```

- [ ] **Step 5: Run all smoke unit tests and the real credential-free smoke**

Run:

```bash
apps/api/.venv/bin/python -m pytest apps/api/tests/test_first_run_smoke.py -v
make smoke
```

Expected: all smoke tests pass; the live smoke prints fixture counts, task-pack export, eight required sections, `promising`, one evidence review, changed evaluation, local-note exclusion, dashboard wiring, and temporary-database cleanup.

- [ ] **Step 6: Commit the proof checkpoint**

```bash
git add scripts/first_run_smoke.py apps/api/tests/test_first_run_smoke.py
git commit -m "test: prove the TaskSignal decision workflow"
```

---

### Task 9: Finalize runtime security, dependency health, v0.2 metadata, and documentation

**Files:**
- Create: `apps/api/tests/test_runtime_config.py`
- Modify: `docker-compose.yml:1-45`
- Modify: `apps/web/package.json:1-12`
- Modify: `apps/web/package-lock.json`
- Modify: `apps/web/Dockerfile:1-10`
- Modify: `.github/workflows/ci.yml:25-45`
- Modify: `.env.example:1-18`
- Modify: `apps/api/pyproject.toml:1-5`
- Modify: `apps/api/uv.lock`
- Modify: `apps/api/app/main.py:31-42`
- Modify: `scripts/release_check.py:1-170`
- Modify: `apps/api/tests/test_release_check.py:1-55`
- Modify: `CHANGELOG.md:1-31`
- Modify: `README.md`
- Modify: `docs/api.md`
- Modify: `docs/model-card.md`
- Modify: `docs/roadmap.md`
- Modify: `docs/demo-evidence.md`
- Modify: `docs/architecture.md`
- Modify: `docs/deployment.md`
- Modify: `docs/threat-model.md`
- Modify: `docs/release-prep.md`

**Interfaces:**
- Consumes: completed v0.2 behavior and proof artifacts.
- Produces: loopback-only default host bindings, reproducible `npm ci`, zero moderate-or-higher npm advisories, version-consistency checks across every metadata source, truthful v0.2 docs, and final release-quality evidence.

- [ ] **Step 1: Write failing runtime and version-consistency tests**

Create `apps/api/tests/test_runtime_config.py`:

```python
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_default_runtime_is_loopback_only_and_reproducible() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text(encoding="utf-8")
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert '"127.0.0.1:5432:5432"' in compose
    assert '"127.0.0.1:8000:8000"' in compose
    assert '"127.0.0.1:3000:3000"' in compose
    assert package["scripts"]["dev"] == "next dev"
    assert package["scripts"]["start"] == "next start -H 0.0.0.0"
    assert "COPY package.json package-lock.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    assert "- run: npm ci" in ci
    assert "- run: npm audit --audit-level=moderate" in ci
```

Add `import json` to `test_release_check.py`. Replace `write_release_files`
with a fixture that writes every version source:

```python
def write_release_files(
    root: Path,
    api_version: str = "1.2.3",
    web_version: str = "1.2.3",
    fastapi_version: str | None = None,
    api_lock_version: str | None = None,
    web_lock_top_version: str | None = None,
    web_lock_root_version: str | None = None,
) -> None:
    fastapi_version = fastapi_version or api_version
    api_lock_version = api_lock_version or api_version
    web_lock_top_version = web_lock_top_version or web_version
    web_lock_root_version = web_lock_root_version or web_version
    api_dir = root / "apps" / "api"
    web_dir = root / "apps" / "web"
    (api_dir / "app").mkdir(parents=True)
    web_dir.mkdir(parents=True)
    (api_dir / "pyproject.toml").write_text(
        f'[project]\nname = "tasksignal-api"\nversion = "{api_version}"\n',
        encoding="utf-8",
    )
    (api_dir / "uv.lock").write_text(
        'version = 1\n\n[[package]]\nname = "tasksignal-api"\n'
        f'version = "{api_lock_version}"\n',
        encoding="utf-8",
    )
    (api_dir / "app" / "main.py").write_text(
        f'app = FastAPI(version="{fastapi_version}")\n',
        encoding="utf-8",
    )
    (web_dir / "package.json").write_text(
        json.dumps({"name": "tasksignal-web", "version": web_version}) + "\n",
        encoding="utf-8",
    )
    (web_dir / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "tasksignal-web",
                "version": web_lock_top_version,
                "lockfileVersion": 3,
                "packages": {
                    "": {
                        "name": "tasksignal-web",
                        "version": web_lock_root_version,
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
```

Add:

```python
def test_project_version_check_rejects_fastapi_and_lock_mismatch(
    tmp_path, monkeypatch
) -> None:
    write_release_files(
        tmp_path,
        fastapi_version="1.2.4",
        api_lock_version="1.2.5",
        web_lock_top_version="1.2.6",
        web_lock_root_version="1.2.7",
    )
    monkeypatch.setattr(release_check, "ROOT", tmp_path)

    _version, failures = release_check.check_project_versions("1.2.3")

    message = " ".join(failures)
    assert "fastapi=1.2.4" in message
    assert "api_lock=1.2.5" in message
    assert "web_lock_top=1.2.6" in message
    assert "web_lock_root=1.2.7" in message
```

- [ ] **Step 2: Run the focused tests and confirm current config/version checks fail**

Run:

```bash
apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_runtime_config.py \
  apps/api/tests/test_release_check.py -v
```

Expected: runtime test FAIL on all-interface ports/`npm install`; version test FAIL because the release checker reads only API and web package versions.

- [ ] **Step 3: Lock down default runtime bindings and reproducible web installs**

Change Compose ports exactly:

```yaml
    ports:
      - "127.0.0.1:5432:5432"
```

```yaml
    ports:
      - "127.0.0.1:8000:8000"
```

```yaml
    ports:
      - "127.0.0.1:3000:3000"
```

Change only the web development script to `"dev": "next dev"`; keep the
container production start script on `0.0.0.0`. Replace the web Docker install
lines with:

```dockerfile
COPY package.json package-lock.json ./
RUN npm ci
```

In `.github/workflows/ci.yml`, replace the frontend install/audit commands with:

```yaml
      - run: npm ci
      - run: npm audit --audit-level=moderate
```

- [ ] **Step 4: Clear current compatible dependency advisories without a framework major upgrade**

Run:

```bash
PATH="/opt/homebrew/opt/node@20/bin:$PATH" \
  npm --prefix apps/web audit fix --package-lock-only --ignore-scripts
git diff -- apps/web/package.json apps/web/package-lock.json
PATH="/opt/homebrew/opt/node@20/bin:$PATH" npm --prefix apps/web ci
PATH="/opt/homebrew/opt/node@20/bin:$PATH" \
  npm --prefix apps/web audit --audit-level=moderate
```

Expected: only compatible lockfile resolution changes (known baseline fixes are
`js-yaml 4.1.1 → 4.3.0` and `undici 7.27.1 → 7.28.0`), `package.json` has no
framework major-version change, `npm ci` exits 0, and audit reports zero
moderate-or-higher vulnerabilities.

- [ ] **Step 5: Strengthen release version consistency checks**

Add imports `ast` and keep `json`, `re`, `tomllib`. Replace
`read_project_versions` in `scripts/release_check.py` with:

```python
def fastapi_version(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg == "version" and isinstance(keyword.value, ast.Constant):
                if isinstance(keyword.value.value, str):
                    return normalize_version(keyword.value.value)
    raise ValueError(f"FastAPI version was not found in {path}")


def read_project_versions() -> dict[str, str]:
    pyproject = tomllib.loads(
        (ROOT / "apps/api/pyproject.toml").read_text(encoding="utf-8")
    )
    uv_lock = tomllib.loads(
        (ROOT / "apps/api/uv.lock").read_text(encoding="utf-8")
    )
    api_lock_package = next(
        package for package in uv_lock["package"] if package["name"] == "tasksignal-api"
    )
    package = json.loads(
        (ROOT / "apps/web/package.json").read_text(encoding="utf-8")
    )
    package_lock = json.loads(
        (ROOT / "apps/web/package-lock.json").read_text(encoding="utf-8")
    )
    return {
        "api": normalize_version(str(pyproject["project"]["version"])),
        "api_lock": normalize_version(str(api_lock_package["version"])),
        "fastapi": fastapi_version(ROOT / "apps/api/app/main.py"),
        "web": normalize_version(str(package["version"])),
        "web_lock_top": normalize_version(str(package_lock["version"])),
        "web_lock_root": normalize_version(
            str(package_lock["packages"][""]["version"])
        ),
    }
```

Keep `check_project_versions` unchanged; it will now compare all six sources.

- [ ] **Step 6: Bump every development version source to 0.2.0**

Apply these exact values:

```toml
# apps/api/pyproject.toml
version = "0.2.0"
```

```python
# apps/api/app/main.py FastAPI constructor
version="0.2.0",
```

```json
// apps/web/package.json and both package-lock root version fields
"version": "0.2.0"
```

Change `.env.example` to:

```env
REDDIT_USER_AGENT=tasksignal-local-demo/0.2
```

Regenerate the API lock root package record without changing dependency
constraints:

```bash
uv lock --project apps/api
```

Add this dated section immediately after `## Unreleased` in `CHANGELOG.md`:

```markdown
## 0.2.0 - 2026-07-09

### Added

- Persistent opportunity decision states and export-excluded local review notes.
- Append-only evidence reviews, transparent evidence readiness, and a selection-biased evaluation report.
- Decision queue filtering, opportunity review controls, and the Evaluation page.
- Decision Context in evidence bundles and Codex task packs.

### Changed

- Local API/web/database host ports bind to loopback by default.
- Development setup uses locked API and web dependencies through `make setup`.
- First-run smoke evidence now proves the complete decision and evidence-review loop.

### Security

- Local review notes remain outside shared exports, and unauthenticated review writes are documented as local-only.
- Compatible frontend dependency advisories were resolved without a framework major upgrade.
```

- [ ] **Step 7: Update behavior and security documentation with exact claims**

Add these bullets to README `What It Does`:

```markdown
- Stores one explicit decision state and an export-excluded local note for each opportunity.
- Keeps evidence reviews append-only and preserves legacy label history without treating unknown labels as current recognized reviews.
- Reports evidence readiness from evidence count, source diversity, safe URL coverage, and human review coverage.
- Shows selection-biased review coverage and precision on reviewed positives without claiming recall, F1, or market validation.
```

Replace the native quickstart setup commands and launch instructions with:

````markdown
```bash
make setup
cp .env.example .env
make doctor
```

`make dev` prints the two native launch commands. Run those commands in
separate terminals:

```bash
cd apps/api
.venv/bin/uvicorn app.main:app --reload
```

```bash
cd apps/web
npm run dev
```

Use `make up` instead to start the loopback-only Docker Compose stack.
````

Add this API contract block to `docs/api.md`:

```markdown
## Decision Workbench

- `GET /api/opportunities?review_state=<state>` optionally filters by one of the six documented decision states.
- `PATCH /api/opportunities/{id}/review` saves `review_state` and an optional local `review_note` of at most 1,000 characters.
- `POST /api/labels` appends one recognized evidence review with an optional 500-character note.
- `GET /api/items/{id}/labels` returns complete newest-first history, including legacy unrecognized labels.
- `GET /api/evaluation` reports reviewable/reviewed counts, coverage, reviewed-positive precision, label counts, and source/signal breakdowns.

Decision and evidence review notes are local annotations and are omitted from evidence and task-pack exports. These write endpoints are unauthenticated local-operator actions, not public collaboration APIs.
```

Replace the model-card evaluation-plan paragraph with:

```markdown
## Human Evaluation

TaskSignal reports coverage over evidence linked to generated opportunities and precision on manually reviewed predicted-positive evidence: `true_signal / (true_signal + false_positive)`. Reviews are selected by the operator, so the report is subject to selection bias and does not represent all detected or undetected items. Recall and F1 are not reported because v0.2 has no reviewed negative population.
```

Add this deployment warning to `docs/deployment.md` and the same boundary to
`docs/threat-model.md`:

```markdown
Docker Compose publishes PostgreSQL, FastAPI, and Next.js on `127.0.0.1` by default. Opportunity decisions and evidence labels are unauthenticated local-operator writes. Do not expose them publicly or to a team until authentication, workspace isolation, retention, and deletion controls exist.

`AUTO_CREATE_TABLES=true` creates missing tables but does not migrate an existing PostgreSQL schema. Run `make migrate` for migration-managed databases. A legacy unversioned Compose volume requires schema inspection and an explicit Alembic stamp/migration plan; do not delete the volume automatically.
```

Update `docs/architecture.md` with the data flow
`opportunity evidence → evidence_review service → readiness/evaluation → API → dashboard/detail/Evaluation/exports`.
Update `docs/roadmap.md` so decision review/evaluation is current v0.2 work, not
a later item. Update `docs/demo-evidence.md` with the exact smoke sequence from
Task 8 and note-exclusion guarantee. Update `docs/release-prep.md` examples to
`0.2.0`. Keep README and `docs/codex-for-oss-application.md` published-release
references at v0.1.3.

- [ ] **Step 8: Run runtime, version, dependency, and documentation checks**

Run:

```bash
apps/api/.venv/bin/python -m pytest \
  apps/api/tests/test_runtime_config.py \
  apps/api/tests/test_release_check.py -v
docker compose config
PATH="/opt/homebrew/opt/node@20/bin:$PATH" \
  npm --prefix apps/web audit --audit-level=moderate
apps/api/.venv/bin/python scripts/release_check.py --version 0.2.0
```

Expected: tests pass; Compose renders all three host bindings on `127.0.0.1`;
npm reports zero moderate-or-higher vulnerabilities; release check reports
version 0.2.0 and no content/version failures.

- [ ] **Step 9: Commit the release-quality checkpoint**

```bash
git add \
  docker-compose.yml \
  apps/web/package.json apps/web/package-lock.json apps/web/Dockerfile \
  .github/workflows/ci.yml .env.example \
  apps/api/pyproject.toml apps/api/uv.lock apps/api/app/main.py \
  scripts/release_check.py \
  apps/api/tests/test_release_check.py apps/api/tests/test_runtime_config.py \
  CHANGELOG.md README.md \
  docs/api.md docs/model-card.md docs/roadmap.md docs/demo-evidence.md \
  docs/architecture.md docs/deployment.md docs/threat-model.md docs/release-prep.md
git commit -m "build: finalize TaskSignal 0.2 release quality"
```

---

### Task 10: Run full verification and browser proof

**Files:**
- Verify only; no planned source edits.

**Interfaces:**
- Consumes: every prior task and the local in-app Browser surface.
- Produces: fresh automated, configuration, Docker-when-available, and interactive evidence for the complete v0.2 workflow.

- [ ] **Step 1: Run the complete automated gate from a fresh dependency state**

Run:

```bash
make setup
make doctor
make verify
make smoke
apps/api/.venv/bin/python scripts/release_check.py --version 0.2.0
PATH="/opt/homebrew/opt/node@20/bin:$PATH" \
  npm --prefix apps/web audit --audit-level=moderate
git diff --check
```

Expected: setup and doctor pass; all backend/frontend tests, ruff, ESLint, and
Next.js build pass; smoke proves the decision loop; release check reports 0.2.0;
audit reports zero moderate-or-higher vulnerabilities; diff check is silent.

- [ ] **Step 2: Validate Compose and run it when the Docker daemon is available**

Always run:

```bash
docker compose config
```

Expected: rendered published bindings are `127.0.0.1:3000`,
`127.0.0.1:8000`, and `127.0.0.1:5432`.

If `docker info` exits 0, run:

```bash
docker compose up --build -d
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:3000/dashboard
lsof -nP -iTCP:3000 -iTCP:8000 -iTCP:5432 -sTCP:LISTEN
docker compose down
```

Expected: API health returns `status=ok`, dashboard returns HTML, and all three
listeners are loopback-only. Never use `docker compose down -v`. If the daemon
is unavailable, record the exact daemon error and retain `docker compose config`
as the verified static boundary.

- [ ] **Step 3: Start the native app for interactive browser verification**

Start the API in one managed terminal session:

```bash
DATABASE_URL=sqlite:///./tasksignal-v02-browser.db \
AUTO_CREATE_TABLES=true \
LLM_PROVIDER=none \
apps/api/.venv/bin/uvicorn app.main:app --app-dir apps/api \
  --host 127.0.0.1 --port 8000
```

Start the web app in a second managed terminal session:

```bash
PATH="/opt/homebrew/opt/node@20/bin:$PATH" \
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 \
npm --prefix apps/web run dev -- --hostname 127.0.0.1 --port 3000
```

Expected: both processes remain running and `http://127.0.0.1:3000/dashboard`
returns HTML.

- [ ] **Step 4: Verify the complete UI with the in-app Browser surface**

Load and follow the Browser control skill, then verify at desktop and narrow
viewport widths:

1. Open `/dashboard` and process fixture data.
2. Confirm six state counts, state badges, readiness badges, and local filtering.
3. Open the top opportunity, save `promising` plus a local note, refresh, and
   confirm persistence.
4. Append a `true_signal` evidence review, confirm history count/readiness
   changes, refresh, and confirm persistence.
5. Open `/evaluation`; confirm coverage, label counts, reviewed precision,
   source/signal breakdowns, bias warning, and no recall/F1 claim.
6. Open task-pack and evidence exports; confirm `Decision Context` and confirm
   neither local note appears.
7. Confirm keyboard focus, labels, error/success messages, table overflow, and
   the eight-item mobile navigation remain usable at a narrow viewport.

Capture screenshots under an ignored temporary artifact directory only if they
materially help verify layout. Do not add generated screenshots to git unless
the user separately requests documentation images.

- [ ] **Step 5: Stop native processes, remove only the temporary browser database, and inspect final state**

Send interrupt to both managed server sessions, then run:

```bash
rm -f \
  tasksignal-v02-browser.db \
  tasksignal-v02-browser.db-shm \
  tasksignal-v02-browser.db-wal
git status --short --branch
git log --oneline -10
```

Expected: no tracked modifications remain; only the pre-existing
`.oss-steward/` and `docs/audits/v0.2-issue-roadmap-2026-06-20.md` may remain
untracked. The log shows the reviewable checkpoints from this plan.

- [ ] **Step 6: Report verified results and explicit residual risks**

Report exact test counts, smoke fixture counts, audit result, release version,
Compose binding evidence, browser flows, commit hashes, and any unavailable
Docker/PostgreSQL verification. State explicitly that v0.2.0 is committed local
development metadata and was not pushed, tagged, or published.

---

## Execution Notes

- Use a fresh implementation subagent for each task and review the diff before
  moving to the next task.
- Run the focused command at every red/green boundary; do not rely on a later
  full-suite pass to prove the test was meaningful.
- Before each commit, run `git diff --check` and stage only the files listed for
  that task.
- Never remove, stage, or rewrite the two pre-existing untracked paths.
- If a task reveals a conflict between this plan and the live repository, stop
  that task, cite the exact mismatch, update the plan/spec deliberately, and
  continue only after the contract is coherent.
