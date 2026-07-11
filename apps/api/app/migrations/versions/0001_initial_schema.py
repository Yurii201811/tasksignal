"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-29
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        embedding_type = sa.Text()
    else:
        embedding_type = sa.JSON()

    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "scan_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("items_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_saved", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "raw_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("raw_json", postgresql.JSONB() if is_postgres else sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "normalized_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("author_hash", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("language", sa.Text(), nullable=False, server_default="en"),
        sa.Column("tags", postgresql.JSONB() if is_postgres else sa.JSON(), nullable=False),
    )
    op.create_index("ix_normalized_items_source", "normalized_items", ["source"])
    op.create_index("ix_normalized_items_text_hash", "normalized_items", ["text_hash"])
    op.create_table(
        "item_signals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("normalized_items.id"), nullable=False),
        sa.Column("is_problem_signal", sa.Boolean(), nullable=False),
        sa.Column("signal_type", sa.Text(), nullable=False),
        sa.Column("pain_score", sa.Float(), nullable=False),
        sa.Column("task_concreteness_score", sa.Float(), nullable=False),
        sa.Column("buying_intent_score", sa.Float(), nullable=False),
        sa.Column(
            "evidence_spans_json", postgresql.JSONB() if is_postgres else sa.JSON(), nullable=False
        ),
        sa.Column("classifier_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_item_signals_is_problem_signal", "item_signals", ["is_problem_signal"])
    op.create_index("ix_item_signals_signal_type", "item_signals", ["signal_type"])
    op.create_table(
        "item_embeddings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("normalized_items.id"), nullable=False),
        sa.Column("embedding", embedding_type, nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    if is_postgres:
        op.execute(
            "ALTER TABLE item_embeddings ALTER COLUMN embedding TYPE vector(384) USING embedding::vector"
        )
        op.execute(
            "CREATE INDEX ix_item_embeddings_vector ON item_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 16)"
        )
    op.create_table(
        "clusters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("centroid_embedding", embedding_type, nullable=True),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    if is_postgres:
        op.execute(
            "ALTER TABLE clusters ALTER COLUMN centroid_embedding TYPE vector(384) USING centroid_embedding::vector"
        )
    op.create_table(
        "cluster_items",
        sa.Column("cluster_id", sa.Uuid(), sa.ForeignKey("clusters.id"), primary_key=True),
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("normalized_items.id"), primary_key=True),
        sa.Column("similarity_score", sa.Float(), nullable=False),
    )
    op.create_table(
        "opportunities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cluster_id", sa.Uuid(), sa.ForeignKey("clusters.id"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("problem_statement", sa.Text(), nullable=False),
        sa.Column("target_user", sa.Text(), nullable=False),
        sa.Column("current_workaround", sa.Text(), nullable=False),
        sa.Column("suggested_mvp", sa.Text(), nullable=False),
        sa.Column("why_now", sa.Text(), nullable=False),
        sa.Column("feasibility_score", sa.Float(), nullable=False),
        sa.Column("opportunity_score", sa.Float(), nullable=False),
        sa.Column("competition_notes", sa.Text(), nullable=False),
        sa.Column(
            "scoring_breakdown_json",
            postgresql.JSONB() if is_postgres else sa.JSON(),
            nullable=False,
        ),
        sa.Column("generated_prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_opportunities_opportunity_score", "opportunities", ["opportunity_score"])
    op.create_table(
        "labels",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("item_id", sa.Uuid(), sa.ForeignKey("normalized_items.id"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in [
        "labels",
        "opportunities",
        "cluster_items",
        "clusters",
        "item_embeddings",
        "item_signals",
        "normalized_items",
        "raw_items",
        "scan_jobs",
        "sources",
    ]:
        op.drop_table(table)
