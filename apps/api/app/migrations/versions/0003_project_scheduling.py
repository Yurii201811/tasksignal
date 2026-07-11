"""add research project scheduling metadata

Revision ID: 0003_project_scheduling
Revises: 0002_research_projects
Create Date: 2026-06-03
"""

import sqlalchemy as sa

from alembic import op

revision = "0003_project_scheduling"
down_revision = "0002_research_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_projects",
        sa.Column("schedule_interval_hours", sa.Integer(), nullable=True),
    )
    op.add_column(
        "research_projects",
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "research_projects",
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "research_projects",
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_research_projects_next_run_at", "research_projects", ["next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_research_projects_next_run_at", table_name="research_projects")
    op.drop_column("research_projects", "run_count")
    op.drop_column("research_projects", "next_run_at")
    op.drop_column("research_projects", "last_run_at")
    op.drop_column("research_projects", "schedule_interval_hours")
