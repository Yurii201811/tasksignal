"""add local workspace settings

Revision ID: 0004_local_workspace_settings
Revises: 0003_project_scheduling
Create Date: 2026-06-03
"""

import sqlalchemy as sa

from alembic import op

revision = "0004_local_workspace_settings"
down_revision = "0003_project_scheduling"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "local_workspace_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("workspace_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("default_source_type", sa.Text(), nullable=False, server_default="hackernews"),
        sa.Column("default_query", sa.Text(), nullable=False, server_default="ask"),
        sa.Column("default_limit", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("default_cadence", sa.Text(), nullable=False, server_default="manual"),
        sa.Column("default_schedule_interval_hours", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("local_workspace_settings")
