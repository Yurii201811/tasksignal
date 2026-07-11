"""add scan outcome fields

Revision ID: 0005_scan_outcomes
Revises: 0004_local_workspace_settings
Create Date: 2026-06-03
"""

import sqlalchemy as sa

from alembic import op

revision = "0005_scan_outcomes"
down_revision = "0004_local_workspace_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "scan_jobs",
        sa.Column("signals_detected", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scan_jobs",
        sa.Column("clusters_created", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "scan_jobs",
        sa.Column("opportunities_created", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("scan_jobs", sa.Column("outcome_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("scan_jobs", "outcome_message")
    op.drop_column("scan_jobs", "opportunities_created")
    op.drop_column("scan_jobs", "clusters_created")
    op.drop_column("scan_jobs", "signals_detected")
