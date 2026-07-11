"""add guarded agent sessions and append-only action audit

Revision ID: 0009_agent_sessions_audit
Revises: 0008_build_packets
Create Date: 2026-07-11
"""

import sqlalchemy as sa

from alembic import op

revision = "0009_agent_sessions_audit"
down_revision = "0008_build_packets"
branch_labels = None
depends_on = None


def lowercase_sha256_check(column: str) -> str:
    return (
        f"length({column}) = 64 AND {column} = lower({column}) AND "
        "length(replace(replace(replace(replace(replace(replace(replace(replace("
        "replace(replace(replace(replace(replace(replace(replace(replace("
        f"{column}, '0', ''), '1', ''), '2', ''), '3', ''), '4', ''), "
        "'5', ''), '6', ''), '7', ''), '8', ''), '9', ''), 'a', ''), 'b', ''), "
        "'c', ''), 'd', ''), 'e', ''), 'f', '')) = 0"
    )


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("process_instance_id", sa.Uuid(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=False),
        sa.Column("client_version", sa.Text(), nullable=True),
        sa.Column("transport", sa.Text(), nullable=False, server_default="stdio"),
        sa.Column("secret_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column(
            "requested_capabilities_json",
            sa.JSON(none_as_null=True),
            nullable=False,
        ),
        sa.Column(
            "approved_capabilities_json",
            sa.JSON(none_as_null=True),
            nullable=False,
        ),
        sa.Column("approval_source", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(trim(client_name)) BETWEEN 1 AND 128",
            name="ck_agent_sessions_client_name",
        ),
        sa.CheckConstraint(
            "client_version IS NULL OR length(trim(client_version)) BETWEEN 1 AND 64",
            name="ck_agent_sessions_client_version",
        ),
        sa.CheckConstraint("transport = 'stdio'", name="ck_agent_sessions_transport"),
        sa.CheckConstraint(
            lowercase_sha256_check("secret_hash"),
            name="ck_agent_sessions_secret_hash",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'revoked', 'expired', 'exited')",
            name="ck_agent_sessions_status",
        ),
        sa.CheckConstraint(
            "approval_source IS NULL OR approval_source IN ('ui', 'interactive_tty')",
            name="ck_agent_sessions_approval_source",
        ),
        sa.CheckConstraint(
            "(approval_source IS NULL AND approved_at IS NULL) OR "
            "(approval_source IS NOT NULL AND approved_at IS NOT NULL)",
            name="ck_agent_sessions_approval_pair",
        ),
        sa.CheckConstraint(
            "last_heartbeat_at IS NOT NULL AND expires_at IS NOT NULL "
            "AND expires_at > last_heartbeat_at",
            name="ck_agent_sessions_lease",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND approval_source IS NULL AND approved_at IS NULL) OR "
            "(status = 'approved' AND approval_source IS NOT NULL AND approved_at IS NOT NULL) OR "
            "status IN ('revoked', 'expired', 'exited')",
            name="ck_agent_sessions_approval_state",
        ),
        sa.CheckConstraint(
            "(status IN ('pending', 'approved') AND revoked_at IS NULL "
            "AND expired_at IS NULL AND exited_at IS NULL) OR "
            "(status = 'revoked' AND revoked_at IS NOT NULL "
            "AND expired_at IS NULL AND exited_at IS NULL) OR "
            "(status = 'expired' AND revoked_at IS NULL "
            "AND expired_at IS NOT NULL AND exited_at IS NULL) OR "
            "(status = 'exited' AND revoked_at IS NULL "
            "AND expired_at IS NULL AND exited_at IS NOT NULL)",
            name="ck_agent_sessions_terminal_state",
        ),
        sa.CheckConstraint("version > 0", name="ck_agent_sessions_version_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "process_instance_id",
            name="uq_agent_sessions_process_instance_id",
        ),
        sa.UniqueConstraint("secret_hash", name="uq_agent_sessions_secret_hash"),
    )
    op.create_index(
        "ix_agent_sessions_status_expires",
        "agent_sessions",
        ["status", "expires_at"],
    )

    op.create_table(
        "agent_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("event_status", sa.Text(), nullable=False),
        sa.Column("idempotency_key_hash", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("capability", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=True),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("request_summary_json", sa.JSON(), nullable=False),
        sa.Column("result_summary_json", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_status IN ('reserved', 'succeeded', 'failed', 'conflict', 'replayed', 'denied')",
            name="ck_agent_actions_event_status",
        ),
        sa.CheckConstraint(
            "(event_status = 'reserved' AND event_sequence = 1) OR "
            "(event_status <> 'reserved' AND event_sequence > 1)",
            name="ck_agent_actions_event_sequence",
        ),
        sa.CheckConstraint(
            lowercase_sha256_check("idempotency_key_hash"),
            name="ck_agent_actions_idempotency_key_hash",
        ),
        sa.CheckConstraint(
            lowercase_sha256_check("request_hash"),
            name="ck_agent_actions_request_hash",
        ),
        sa.CheckConstraint(
            "length(trim(capability)) BETWEEN 1 AND 128",
            name="ck_agent_actions_capability",
        ),
        sa.CheckConstraint(
            "length(trim(tool_name)) BETWEEN 1 AND 128",
            name="ck_agent_actions_tool_name",
        ),
        sa.CheckConstraint(
            "target_type IS NULL OR length(trim(target_type)) BETWEEN 1 AND 128",
            name="ck_agent_actions_target_type",
        ),
        sa.CheckConstraint(
            "target_id IS NULL OR length(trim(target_id)) BETWEEN 1 AND 256",
            name="ck_agent_actions_target_id",
        ),
        sa.CheckConstraint(
            "length(CAST(request_summary_json AS TEXT)) <= 4096",
            name="ck_agent_actions_request_summary_bounded",
        ),
        sa.CheckConstraint(
            "result_summary_json IS NULL OR length(CAST(result_summary_json AS TEXT)) <= 4096",
            name="ck_agent_actions_result_summary_bounded",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR length(trim(error_code)) BETWEEN 1 AND 128",
            name="ck_agent_actions_error_code",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["agent_sessions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operation_id",
            "event_sequence",
            name="uq_agent_actions_operation_sequence",
        ),
    )
    op.create_index("ix_agent_actions_session_id", "agent_actions", ["session_id"])
    op.create_index("ix_agent_actions_operation_id", "agent_actions", ["operation_id"])
    op.create_index(
        "ix_agent_actions_session_created",
        "agent_actions",
        ["session_id", "created_at", "id"],
    )
    op.create_index(
        "ix_agent_actions_operation_sequence",
        "agent_actions",
        ["operation_id", "event_sequence"],
    )
    op.create_index(
        "ix_agent_actions_correlation_id",
        "agent_actions",
        ["correlation_id"],
    )
    op.create_index(
        "uq_agent_actions_reserved_key",
        "agent_actions",
        ["session_id", "idempotency_key_hash"],
        unique=True,
        sqlite_where=sa.text("event_status = 'reserved'"),
        postgresql_where=sa.text("event_status = 'reserved'"),
    )
    op.create_index(
        "uq_agent_actions_terminal_operation",
        "agent_actions",
        ["operation_id"],
        unique=True,
        sqlite_where=sa.text("event_status IN ('succeeded', 'failed', 'denied')"),
        postgresql_where=sa.text("event_status IN ('succeeded', 'failed', 'denied')"),
    )

    with op.batch_alter_table("research_projects") as batch_op:
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch_op.create_check_constraint(
            "ck_research_projects_version_positive",
            "version > 0",
        )

    with op.batch_alter_table("labels") as batch_op:
        batch_op.add_column(
            sa.Column("actor_type", sa.Text(), nullable=False, server_default="human")
        )
        batch_op.add_column(sa.Column("agent_session_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("version", sa.Integer(), nullable=True))

    # Existing labels are human-authored. Preserve their complete history and assign
    # deterministic per-item versions without inferring agent provenance.
    op.execute(
        sa.text(
            "UPDATE labels SET version = ("
            "SELECT count(*) FROM labels AS older "
            "WHERE older.item_id = labels.item_id AND ("
            "older.created_at < labels.created_at OR ("
            "older.created_at = labels.created_at AND "
            "CAST(older.id AS VARCHAR(64)) <= CAST(labels.id AS VARCHAR(64)))))"
        )
    )

    with op.batch_alter_table("labels") as batch_op:
        batch_op.alter_column(
            "version",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="1",
        )
        batch_op.create_check_constraint(
            "ck_labels_actor_type",
            "actor_type IN ('human', 'agent')",
        )
        batch_op.create_check_constraint(
            "ck_labels_actor_session",
            "(actor_type = 'agent' AND agent_session_id IS NOT NULL) OR "
            "(actor_type = 'human' AND agent_session_id IS NULL)",
        )
        batch_op.create_check_constraint("ck_labels_version_positive", "version > 0")
        batch_op.create_unique_constraint(
            "uq_labels_item_version",
            ["item_id", "version"],
        )
        batch_op.create_foreign_key(
            "fk_labels_agent_session_id_agent_sessions",
            "agent_sessions",
            ["agent_session_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index("ix_labels_agent_session_id", ["agent_session_id"])

    with op.batch_alter_table("opportunity_decision_events") as batch_op:
        batch_op.add_column(sa.Column("agent_session_id", sa.Uuid(), nullable=True))
        batch_op.create_check_constraint(
            "ck_opportunity_decision_events_actor_session",
            "(actor_type = 'agent' AND agent_session_id IS NOT NULL) OR "
            "(actor_type IN ('system', 'human') AND agent_session_id IS NULL)",
        )
        batch_op.create_foreign_key(
            "fk_opportunity_decision_events_agent_session_id_agent_sessions",
            "agent_sessions",
            ["agent_session_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_index(
            "ix_opportunity_decision_events_agent_session_id",
            ["agent_session_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("opportunity_decision_events") as batch_op:
        batch_op.drop_index("ix_opportunity_decision_events_agent_session_id")
        batch_op.drop_constraint(
            "fk_opportunity_decision_events_agent_session_id_agent_sessions",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "ck_opportunity_decision_events_actor_session",
            type_="check",
        )
        batch_op.drop_column("agent_session_id")

    with op.batch_alter_table("labels") as batch_op:
        batch_op.drop_index("ix_labels_agent_session_id")
        batch_op.drop_constraint(
            "fk_labels_agent_session_id_agent_sessions",
            type_="foreignkey",
        )
        batch_op.drop_constraint("uq_labels_item_version", type_="unique")
        batch_op.drop_constraint("ck_labels_version_positive", type_="check")
        batch_op.drop_constraint("ck_labels_actor_session", type_="check")
        batch_op.drop_constraint("ck_labels_actor_type", type_="check")
        batch_op.drop_column("version")
        batch_op.drop_column("agent_session_id")
        batch_op.drop_column("actor_type")

    with op.batch_alter_table("research_projects") as batch_op:
        batch_op.drop_constraint("ck_research_projects_version_positive", type_="check")
        batch_op.drop_column("version")

    op.drop_index("uq_agent_actions_terminal_operation", table_name="agent_actions")
    op.drop_index("uq_agent_actions_reserved_key", table_name="agent_actions")
    op.drop_index("ix_agent_actions_correlation_id", table_name="agent_actions")
    op.drop_index("ix_agent_actions_operation_sequence", table_name="agent_actions")
    op.drop_index("ix_agent_actions_session_created", table_name="agent_actions")
    op.drop_index("ix_agent_actions_operation_id", table_name="agent_actions")
    op.drop_index("ix_agent_actions_session_id", table_name="agent_actions")
    op.drop_table("agent_actions")
    op.drop_index("ix_agent_sessions_status_expires", table_name="agent_sessions")
    op.drop_table("agent_sessions")
