"""add research projects

Revision ID: 0002_research_projects
Revises: 0001_initial_schema
Create Date: 2026-06-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_research_projects"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    json_type = postgresql.JSONB() if is_postgres else sa.JSON()

    op.create_table(
        "research_projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False, server_default=""),
        sa.Column("limit", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("cadence", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("labels_json", json_type, nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_scan_id", sa.Uuid(), sa.ForeignKey("scan_jobs.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_research_projects_source_type", "research_projects", ["source_type"])


def downgrade() -> None:
    op.drop_index("ix_research_projects_source_type", table_name="research_projects")
    op.drop_table("research_projects")
