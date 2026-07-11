"""add research run lineage

Revision ID: 0007_research_memory
Revises: 0006_decision_workbench
Create Date: 2026-07-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0007_research_memory"
down_revision = "0006_decision_workbench"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_project_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("requested_limit", sa.Integer(), nullable=False),
        sa.Column(
            "lineage_complete",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sequence > 0", name="ck_research_project_runs_sequence_positive"),
        sa.CheckConstraint(
            "requested_limit BETWEEN 1 AND 100",
            name="ck_research_project_runs_requested_limit",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["research_projects.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["scan_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "sequence",
            name="uq_research_project_runs_project_sequence",
        ),
    )
    op.create_index(
        "ix_research_project_runs_project_id",
        "research_project_runs",
        ["project_id"],
    )
    op.create_index(
        "ix_research_project_runs_scan_id",
        "research_project_runs",
        ["scan_id"],
        unique=True,
    )

    op.create_table(
        "scan_items",
        sa.Column("scan_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_in_scan",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["scan_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["normalized_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("scan_id", "item_id"),
    )
    op.create_index("ix_scan_items_item_scan", "scan_items", ["item_id", "scan_id"])

    with op.batch_alter_table("clusters") as batch_op:
        batch_op.add_column(sa.Column("scan_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_clusters_scan_id_scan_jobs",
            "scan_jobs",
            ["scan_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_clusters_scan_id", ["scan_id"])
    with op.batch_alter_table("opportunities") as batch_op:
        batch_op.add_column(sa.Column("scan_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_opportunities_scan_id_scan_jobs",
            "scan_jobs",
            ["scan_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_opportunities_scan_id", ["scan_id"])


def downgrade() -> None:
    with op.batch_alter_table("opportunities") as batch_op:
        batch_op.drop_index("ix_opportunities_scan_id")
        batch_op.drop_constraint(
            "fk_opportunities_scan_id_scan_jobs",
            type_="foreignkey",
        )
        batch_op.drop_column("scan_id")
    with op.batch_alter_table("clusters") as batch_op:
        batch_op.drop_index("ix_clusters_scan_id")
        batch_op.drop_constraint("fk_clusters_scan_id_scan_jobs", type_="foreignkey")
        batch_op.drop_column("scan_id")
    op.drop_index("ix_scan_items_item_scan", table_name="scan_items")
    op.drop_table("scan_items")
    op.drop_index("ix_research_project_runs_scan_id", table_name="research_project_runs")
    op.drop_index("ix_research_project_runs_project_id", table_name="research_project_runs")
    op.drop_table("research_project_runs")
