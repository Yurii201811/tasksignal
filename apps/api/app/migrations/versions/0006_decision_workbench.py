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
