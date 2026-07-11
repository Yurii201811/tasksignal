"""add persistent opportunity threads

Revision ID: 0007_opportunity_threads
Revises: 0007_research_memory
Create Date: 2026-07-11
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "0007_opportunity_threads"
down_revision = "0007_research_memory"
branch_labels = None
depends_on = None

REVIEW_STATES = (
    "new",
    "needs_more_evidence",
    "promising",
    "rejected",
    "duplicate",
    "build_candidate",
)
MATCH_METHODS = (
    "legacy_backfill",
    "new_untracked",
    "new_no_candidates",
    "new_below_threshold",
    "new_ambiguous",
    "exact_evidence",
    "weighted_similarity",
    "manual_detach",
    "regenerated",
    "enhanced",
)


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def digest(prefix: bytes, value: Any) -> str:
    return hashlib.sha256(prefix + b"\0" + canonical_json(value)).hexdigest()


def backfill_opportunity_threads() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    opportunities = sa.Table("opportunities", metadata, autoload_with=bind)
    threads = sa.Table("opportunity_threads", metadata, autoload_with=bind)
    events = sa.Table("opportunity_decision_events", metadata, autoload_with=bind)
    runs = sa.Table("research_project_runs", metadata, autoload_with=bind)
    cluster_items = sa.Table("cluster_items", metadata, autoload_with=bind)
    normalized_items = sa.Table("normalized_items", metadata, autoload_with=bind)

    def generated_uuid() -> uuid.UUID | str:
        value = uuid.uuid4()
        return value if bind.dialect.name == "postgresql" else value.hex

    rows = bind.execute(sa.select(opportunities)).mappings().all()
    migration_time = datetime.now(UTC)
    for row in rows:
        run_id = None
        project_id = None
        lineage_status = "untracked"
        if row["scan_id"] is not None:
            linked_run = (
                bind.execute(
                    sa.select(runs.c.id, runs.c.project_id, runs.c.lineage_complete).where(
                        runs.c.scan_id == row["scan_id"]
                    )
                )
                .mappings()
                .one_or_none()
            )
            if linked_run is not None and linked_run["lineage_complete"]:
                run_id = linked_run["id"]
                project_id = linked_run["project_id"]
                lineage_status = "complete"

        evidence_rows = bind.execute(
            sa.select(normalized_items.c.text_hash)
            .select_from(
                cluster_items.join(
                    normalized_items,
                    normalized_items.c.id == cluster_items.c.item_id,
                )
            )
            .where(cluster_items.c.cluster_id == row["cluster_id"])
        ).all()
        evidence_hashes = sorted({entry.text_hash for entry in evidence_rows})
        evidence_hash = digest(b"tasksignal:evidence-set:v1", evidence_hashes)
        content_payload = {
            "competition_notes": row["competition_notes"],
            "current_workaround": row["current_workaround"],
            "evidence_hash": evidence_hash,
            "feasibility_score": row["feasibility_score"],
            "generated_prompt": row["generated_prompt"],
            "opportunity_score": row["opportunity_score"],
            "problem_statement": row["problem_statement"],
            "scoring_breakdown": row["scoring_breakdown_json"],
            "suggested_mvp": row["suggested_mvp"],
            "target_user": row["target_user"],
            "title": row["title"],
            "why_now": row["why_now"],
        }
        content_hash = digest(b"tasksignal:opportunity-content:v1", content_payload)
        thread_id = generated_uuid()
        thread_created_at = row["created_at"] or migration_time
        thread_updated_at = row["decision_updated_at"] or row["updated_at"] or migration_time

        bind.execute(
            threads.insert().values(
                id=thread_id,
                project_id=project_id,
                current_snapshot_id=row["id"],
                lineage_status=lineage_status,
                review_state=row["review_state"] or "new",
                review_note=row["review_note"],
                decision_updated_at=row["decision_updated_at"],
                version=1,
                created_at=thread_created_at,
                updated_at=thread_updated_at,
            )
        )
        bind.execute(
            opportunities.update()
            .where(opportunities.c.id == row["id"])
            .values(
                thread_id=thread_id,
                run_id=run_id,
                evidence_hash=evidence_hash,
                content_hash=content_hash,
                match_method="legacy_backfill",
                match_confidence=None,
                match_margin=None,
                centroid_similarity=None,
                evidence_jaccard=None,
                title_jaccard=None,
                embedding_model=None,
                embedding_backend=None,
            )
        )
        bind.execute(
            events.insert().values(
                id=generated_uuid(),
                thread_id=thread_id,
                event_type="legacy_backfill",
                actor_type="system",
                snapshot_id=row["id"],
                related_thread_id=None,
                previous_state=None,
                next_state=row["review_state"] or "new",
                previous_note=None,
                next_note=row["review_note"],
                details_json={"lineage_status": lineage_status},
                created_at=migration_time,
            )
        )

    opportunity_count = bind.scalar(sa.select(sa.func.count()).select_from(opportunities)) or 0
    thread_count = bind.scalar(sa.select(sa.func.count()).select_from(threads)) or 0
    event_count = bind.scalar(sa.select(sa.func.count()).select_from(events)) or 0
    if opportunity_count != thread_count or opportunity_count != event_count:
        raise RuntimeError("Opportunity thread backfill did not preserve one-to-one lineage")


def upgrade() -> None:
    review_values = ", ".join(f"'{value}'" for value in REVIEW_STATES)
    op.create_table(
        "opportunity_threads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("current_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("lineage_status", sa.Text(), nullable=False),
        sa.Column("review_state", sa.Text(), nullable=False, server_default="new"),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("decision_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_opportunity_threads_version_positive"),
        sa.CheckConstraint(
            "lineage_status IN ('complete', 'untracked')",
            name="ck_opportunity_threads_lineage_status",
        ),
        sa.CheckConstraint(
            f"review_state IN ({review_values})",
            name="ck_opportunity_threads_review_state",
        ),
        sa.CheckConstraint(
            "(project_id IS NULL AND lineage_status = 'untracked') OR "
            "(project_id IS NOT NULL AND lineage_status = 'complete')",
            name="ck_opportunity_threads_project_lineage",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["research_projects.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["current_snapshot_id"],
            ["opportunities.id"],
            name="fk_opportunity_threads_current_snapshot_id_opportunities",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("current_snapshot_id", name="uq_opportunity_threads_current_snapshot"),
    )
    op.create_index("ix_opportunity_threads_project_id", "opportunity_threads", ["project_id"])
    op.create_index("ix_opportunity_threads_review_state", "opportunity_threads", ["review_state"])
    op.create_index(
        "ix_opportunity_threads_project_review",
        "opportunity_threads",
        ["project_id", "review_state"],
    )

    for name, column_type in (
        ("thread_id", sa.Uuid()),
        ("run_id", sa.Uuid()),
        ("evidence_hash", sa.Text()),
        ("content_hash", sa.Text()),
        ("match_method", sa.Text()),
        ("match_confidence", sa.Float()),
        ("match_margin", sa.Float()),
        ("centroid_similarity", sa.Float()),
        ("evidence_jaccard", sa.Float()),
        ("title_jaccard", sa.Float()),
        ("embedding_model", sa.Text()),
        ("embedding_backend", sa.Text()),
    ):
        op.add_column("opportunities", sa.Column(name, column_type, nullable=True))

    op.create_table(
        "opportunity_decision_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("related_thread_id", sa.Uuid(), nullable=True),
        sa.Column("previous_state", sa.Text(), nullable=True),
        sa.Column("next_state", sa.Text(), nullable=True),
        sa.Column("previous_note", sa.Text(), nullable=True),
        sa.Column("next_note", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('legacy_backfill', 'decision_changed', "
            "'snapshot_detached', 'thread_created_by_detach')",
            name="ck_opportunity_decision_events_type",
        ),
        sa.CheckConstraint(
            "actor_type IN ('system', 'human', 'agent')",
            name="ck_opportunity_decision_events_actor",
        ),
        sa.ForeignKeyConstraint(["thread_id"], ["opportunity_threads.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["snapshot_id"], ["opportunities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["related_thread_id"], ["opportunity_threads.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_opportunity_decision_events_thread_id",
        "opportunity_decision_events",
        ["thread_id"],
    )
    op.create_index(
        "ix_opportunity_decision_events_thread_created",
        "opportunity_decision_events",
        ["thread_id", "created_at", "id"],
    )

    backfill_opportunity_threads()

    match_values = ", ".join(f"'{value}'" for value in MATCH_METHODS)
    with op.batch_alter_table("opportunities") as batch_op:
        batch_op.alter_column("thread_id", existing_type=sa.Uuid(), nullable=False)
        batch_op.alter_column("evidence_hash", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column("content_hash", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column("match_method", existing_type=sa.Text(), nullable=False)
        batch_op.create_foreign_key(
            "fk_opportunities_thread_id_opportunity_threads",
            "opportunity_threads",
            ["thread_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_opportunities_run_id_research_project_runs",
            "research_project_runs",
            ["run_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_opportunities_thread_id", ["thread_id"])
        batch_op.create_index("ix_opportunities_run_id", ["run_id"])
        batch_op.create_index("ix_opportunities_evidence_hash", ["evidence_hash"])
        batch_op.create_index("ix_opportunities_thread_created", ["thread_id", "created_at", "id"])
        batch_op.create_index("ix_opportunities_run_thread", ["run_id", "thread_id"])
        batch_op.create_check_constraint(
            "ck_opportunities_match_method",
            f"match_method IN ({match_values})",
        )
        for column in (
            "match_confidence",
            "match_margin",
            "centroid_similarity",
            "evidence_jaccard",
            "title_jaccard",
        ):
            batch_op.create_check_constraint(
                f"ck_opportunities_{column}",
                f"{column} IS NULL OR ({column} >= 0 AND {column} <= 1)",
            )
        batch_op.create_check_constraint(
            "ck_opportunities_embedding_identity",
            "(embedding_model IS NULL AND embedding_backend IS NULL) OR "
            "(embedding_model IS NOT NULL AND embedding_backend IS NOT NULL)",
        )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_decision_events_thread_created",
        table_name="opportunity_decision_events",
    )
    op.drop_index(
        "ix_opportunity_decision_events_thread_id",
        table_name="opportunity_decision_events",
    )
    op.drop_table("opportunity_decision_events")
    op.execute(sa.text("UPDATE opportunity_threads SET current_snapshot_id = NULL"))

    with op.batch_alter_table("opportunities") as batch_op:
        batch_op.drop_constraint("ck_opportunities_embedding_identity", type_="check")
        for column in reversed(
            (
                "match_confidence",
                "match_margin",
                "centroid_similarity",
                "evidence_jaccard",
                "title_jaccard",
            )
        ):
            batch_op.drop_constraint(f"ck_opportunities_{column}", type_="check")
        batch_op.drop_constraint("ck_opportunities_match_method", type_="check")
        batch_op.drop_index("ix_opportunities_run_thread")
        batch_op.drop_index("ix_opportunities_thread_created")
        batch_op.drop_index("ix_opportunities_evidence_hash")
        batch_op.drop_index("ix_opportunities_run_id")
        batch_op.drop_index("ix_opportunities_thread_id")
        batch_op.drop_constraint(
            "fk_opportunities_run_id_research_project_runs", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_opportunities_thread_id_opportunity_threads", type_="foreignkey"
        )
        for column in (
            "embedding_backend",
            "embedding_model",
            "title_jaccard",
            "evidence_jaccard",
            "centroid_similarity",
            "match_margin",
            "match_confidence",
            "match_method",
            "content_hash",
            "evidence_hash",
            "run_id",
            "thread_id",
        ):
            batch_op.drop_column(column)

    op.drop_index("ix_opportunity_threads_project_review", table_name="opportunity_threads")
    op.drop_index("ix_opportunity_threads_review_state", table_name="opportunity_threads")
    op.drop_index("ix_opportunity_threads_project_id", table_name="opportunity_threads")
    op.drop_table("opportunity_threads")
