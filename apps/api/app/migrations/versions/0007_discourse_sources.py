"""add Discourse source authorization and runtime state

Revision ID: 0007_discourse_sources
Revises: 0007_opportunity_threads
Create Date: 2026-07-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0007_discourse_sources"
down_revision = "0007_opportunity_threads"
branch_labels = None
depends_on = None

FAILURE_CODES = (
    "timeout",
    "connection",
    "dns_rejected",
    "redirect_rejected",
    "http_error",
    "rate_limited",
    "response_too_large",
    "invalid_response",
)


def upgrade() -> None:
    failure_values = ", ".join(f"'{value}'" for value in FAILURE_CODES)
    op.create_table(
        "discourse_source_state",
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("scheme", sa.Text(), nullable=False, server_default="https"),
        sa.Column("host", sa.Text(), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="443"),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terms_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_code", sa.Text(), nullable=True),
        sa.Column("last_failure_message", sa.Text(), nullable=True),
        sa.Column("last_http_status", sa.Integer(), nullable=True),
        sa.Column("retry_after_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("scheme = 'https'", name="ck_discourse_source_state_https"),
        sa.CheckConstraint(
            "length(host) > 0 AND host = lower(host)",
            name="ck_discourse_source_state_host_canonical",
        ),
        sa.CheckConstraint(
            "port >= 1 AND port <= 65535",
            name="ck_discourse_source_state_port",
        ),
        sa.CheckConstraint(
            "(authorized_at IS NULL AND terms_confirmed_at IS NULL) OR "
            "(authorized_at IS NOT NULL AND terms_confirmed_at IS NOT NULL)",
            name="ck_discourse_source_state_terms_authorization",
        ),
        sa.CheckConstraint(
            f"last_failure_code IS NULL OR last_failure_code IN ({failure_values})",
            name="ck_discourse_source_state_failure_code",
        ),
        sa.CheckConstraint(
            "last_failure_message IS NULL OR length(last_failure_message) <= 500",
            name="ck_discourse_source_state_failure_message",
        ),
        sa.CheckConstraint(
            "last_http_status IS NULL OR (last_http_status >= 100 AND last_http_status <= 599)",
            name="ck_discourse_source_state_http_status",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id"),
        sa.UniqueConstraint(
            "host",
            "port",
            name="uq_discourse_source_state_host_port",
        ),
    )

    with op.batch_alter_table("research_projects") as batch_op:
        batch_op.add_column(sa.Column("source_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_research_projects_source_id_sources",
            "sources",
            ["source_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_research_projects_source_id", ["source_id"])

    with op.batch_alter_table("research_project_runs") as batch_op:
        batch_op.add_column(sa.Column("source_origin", sa.Text(), nullable=True))

    with op.batch_alter_table("scan_items") as batch_op:
        batch_op.add_column(sa.Column("observed_source", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("observed_external_id", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("observed_url", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("scan_items") as batch_op:
        batch_op.drop_column("observed_url")
        batch_op.drop_column("observed_external_id")
        batch_op.drop_column("observed_source")

    with op.batch_alter_table("research_project_runs") as batch_op:
        batch_op.drop_column("source_origin")

    with op.batch_alter_table("research_projects") as batch_op:
        batch_op.drop_index("ix_research_projects_source_id")
        batch_op.drop_constraint(
            "fk_research_projects_source_id_sources",
            type_="foreignkey",
        )
        batch_op.drop_column("source_id")

    op.drop_table("discourse_source_state")
