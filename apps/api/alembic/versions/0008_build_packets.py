"""add immutable build packet snapshots

Revision ID: 0008_build_packets
Revises: 0007_discourse_sources
Create Date: 2026-07-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0008_build_packets"
down_revision = "0007_discourse_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("research_project_runs") as batch_op:
        batch_op.create_unique_constraint(
            "uq_research_project_runs_id_project",
            ["id", "project_id"],
        )

    with op.batch_alter_table("opportunity_threads") as batch_op:
        batch_op.create_unique_constraint(
            "uq_opportunity_threads_id_project",
            ["id", "project_id"],
        )
        batch_op.create_unique_constraint(
            "uq_opportunity_threads_id_lineage",
            ["id", "lineage_status"],
        )

    with op.batch_alter_table("opportunities") as batch_op:
        batch_op.create_unique_constraint(
            "uq_opportunities_id_thread_id",
            ["id", "thread_id"],
        )

    op.create_table(
        "build_packets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), nullable=False),
        sa.Column("lineage_status", sa.Text(), nullable=False),
        sa.Column("generation_mode", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("tasksignal_version", sa.Text(), nullable=False),
        sa.Column("template_version", sa.Text(), nullable=False),
        sa.Column("source_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("artifacts_json", sa.JSON(), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.Text(), nullable=False),
        sa.Column("enhancement_status", sa.Text(), nullable=False),
        sa.Column("enhanced_artifacts_json", sa.JSON(), nullable=True),
        sa.Column("enhancement_provider", sa.Text(), nullable=True),
        sa.Column("enhancement_model", sa.Text(), nullable=True),
        sa.Column("enhancement_template_version", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "generation_mode IN ('deterministic', 'configured_ai')",
            name="ck_build_packets_generation_mode",
        ),
        sa.CheckConstraint(
            "enhancement_status IN ('not_requested', 'generated', 'fallback')",
            name="ck_build_packets_enhancement_status",
        ),
        sa.CheckConstraint(
            "(project_id IS NULL AND run_id IS NULL) OR "
            "(project_id IS NOT NULL AND run_id IS NOT NULL)",
            name="ck_build_packets_project_run_linkage",
        ),
        sa.CheckConstraint(
            "(lineage_status = 'untracked' AND project_id IS NULL AND run_id IS NULL) OR "
            "(lineage_status = 'complete' AND project_id IS NOT NULL AND run_id IS NOT NULL)",
            name="ck_build_packets_lineage_shape",
        ),
        sa.CheckConstraint(
            "length(trim(schema_version)) BETWEEN 1 AND 128 AND "
            "length(trim(tasksignal_version)) BETWEEN 1 AND 64 AND "
            "length(trim(template_version)) BETWEEN 1 AND 128",
            name="ck_build_packets_versions_nonempty",
        ),
        sa.CheckConstraint(
            "length(manifest_sha256) = 64 AND manifest_sha256 = lower(manifest_sha256) "
            "AND length(replace(replace(replace(replace(replace(replace(replace(replace("
            "replace(replace(replace(replace(replace(replace(replace(replace("
            "manifest_sha256, '0', ''), '1', ''), '2', ''), '3', ''), '4', ''), "
            "'5', ''), '6', ''), '7', ''), '8', ''), '9', ''), 'a', ''), 'b', ''), "
            "'c', ''), 'd', ''), 'e', ''), 'f', '')) = 0",
            name="ck_build_packets_manifest_sha256",
        ),
        sa.CheckConstraint(
            "enhancement_provider IS NULL OR "
            "length(trim(enhancement_provider)) BETWEEN 1 AND 128",
            name="ck_build_packets_enhancement_provider_nonempty",
        ),
        sa.CheckConstraint(
            "enhancement_model IS NULL OR "
            "length(trim(enhancement_model)) BETWEEN 1 AND 256",
            name="ck_build_packets_enhancement_model_nonempty",
        ),
        sa.CheckConstraint(
            "enhancement_template_version IS NULL OR "
            "length(trim(enhancement_template_version)) BETWEEN 1 AND 128",
            name="ck_build_packets_enhancement_template_nonempty",
        ),
        sa.CheckConstraint(
            "(generation_mode = 'deterministic' AND "
            "enhancement_status = 'not_requested' AND "
            "enhanced_artifacts_json IS NULL AND enhancement_provider IS NULL AND "
            "enhancement_model IS NULL AND enhancement_template_version IS NULL) OR "
            "(generation_mode = 'configured_ai' AND "
            "enhancement_provider IS NOT NULL AND enhancement_model IS NOT NULL AND "
            "enhancement_template_version IS NOT NULL AND "
            "((enhancement_status = 'generated' AND enhanced_artifacts_json IS NOT NULL) OR "
            "(enhancement_status = 'fallback' AND enhanced_artifacts_json IS NULL)))",
            name="ck_build_packets_enhancement_shape",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["research_projects.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["research_project_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["opportunity_threads.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "thread_id"],
            ["opportunities.id", "opportunities.thread_id"],
            name="fk_build_packets_snapshot_thread_opportunities",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["research_project_runs.id", "research_project_runs.project_id"],
            name="fk_build_packets_run_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id", "project_id"],
            ["opportunity_threads.id", "opportunity_threads.project_id"],
            name="fk_build_packets_thread_project",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["thread_id", "lineage_status"],
            ["opportunity_threads.id", "opportunity_threads.lineage_status"],
            name="fk_build_packets_thread_lineage",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_build_packets_project_created",
        "build_packets",
        ["project_id", "created_at", "id"],
    )
    op.create_index("ix_build_packets_run_id", "build_packets", ["run_id"])
    op.create_index(
        "ix_build_packets_thread_created",
        "build_packets",
        ["thread_id", "created_at", "id"],
    )
    op.create_index("ix_build_packets_snapshot_id", "build_packets", ["snapshot_id"])


def downgrade() -> None:
    op.drop_index("ix_build_packets_snapshot_id", table_name="build_packets")
    op.drop_index("ix_build_packets_thread_created", table_name="build_packets")
    op.drop_index("ix_build_packets_run_id", table_name="build_packets")
    op.drop_index("ix_build_packets_project_created", table_name="build_packets")
    op.drop_table("build_packets")

    with op.batch_alter_table("opportunities") as batch_op:
        batch_op.drop_constraint("uq_opportunities_id_thread_id", type_="unique")

    with op.batch_alter_table("opportunity_threads") as batch_op:
        batch_op.drop_constraint("uq_opportunity_threads_id_lineage", type_="unique")
        batch_op.drop_constraint("uq_opportunity_threads_id_project", type_="unique")

    with op.batch_alter_table("research_project_runs") as batch_op:
        batch_op.drop_constraint("uq_research_project_runs_id_project", type_="unique")
