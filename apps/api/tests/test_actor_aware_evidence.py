from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.api.routes import opportunity_to_out
from app.models.all_models import (
    AgentSession,
    ClusterItem,
    Label,
    NormalizedItem,
    Opportunity,
)
from app.services.agent_sessions import STANDARD_WRITE_CAPABILITIES, hash_session_secret
from app.services.evidence_review.service import (
    evaluation_summary,
    get_agent_review_snapshots,
    get_review_snapshots,
    unresolved_sensitive_risk,
)
from app.workers.demo_pipeline import process_demo

NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


def reviewable_item_id(db_session):
    return db_session.scalar(
        select(NormalizedItem.id)
        .join(ClusterItem, ClusterItem.item_id == NormalizedItem.id)
        .join(Opportunity, Opportunity.cluster_id == ClusterItem.cluster_id)
        .limit(1)
    )


def approved_session() -> AgentSession:
    return AgentSession(
        process_instance_id=uuid4(),
        client_name="Actor-aware test",
        client_version="1.0",
        transport="stdio",
        secret_hash=hash_session_secret("actor-aware-session-secret"),
        status="approved",
        requested_capabilities_json=sorted(STANDARD_WRITE_CAPABILITIES),
        approved_capabilities_json=sorted(STANDARD_WRITE_CAPABILITIES),
        approval_source="ui",
        approved_at=NOW,
        last_heartbeat_at=NOW,
        expires_at=NOW + timedelta(seconds=60),
        version=2,
        created_at=NOW,
        updated_at=NOW,
    )


def test_agent_labels_are_distinct_and_do_not_grade_human_precision(db_session) -> None:
    process_demo(db_session)
    item_id = reviewable_item_id(db_session)
    assert item_id is not None
    session = approved_session()
    db_session.add(session)
    db_session.flush()
    db_session.add_all(
        [
            Label(
                item_id=item_id,
                label="true_signal",
                actor_type="human",
                agent_session_id=None,
                version=1,
                created_at=NOW,
            ),
            Label(
                item_id=item_id,
                label="false_positive",
                actor_type="agent",
                agent_session_id=session.id,
                version=2,
                created_at=NOW + timedelta(seconds=1),
            ),
        ]
    )
    db_session.commit()

    human = get_review_snapshots(db_session, [item_id])[item_id]
    agent = get_agent_review_snapshots(db_session, [item_id])[item_id]
    summary = evaluation_summary(db_session)
    opportunity = db_session.scalar(
        select(Opportunity)
        .join(ClusterItem, ClusterItem.cluster_id == Opportunity.cluster_id)
        .where(ClusterItem.item_id == item_id)
        .limit(1)
    )
    assert opportunity is not None
    item_output = next(
        item for item in opportunity_to_out(db_session, opportunity).evidence_items
        if item.id == item_id
    )

    assert human.review_label == "true_signal"
    assert human.actor_type == "human"
    assert human.version == 1
    assert agent.review_label == "false_positive"
    assert agent.actor_type == "agent"
    assert agent.agent_session_id == session.id
    assert item_output.review_version == 1
    assert item_output.agent_review_version == 2
    assert summary.label_counts.true_signal == 1
    assert summary.label_counts.false_positive == 0
    assert summary.precision_on_reviewed_positives == 1.0


def test_later_human_label_clears_newer_agent_sensitive_risk(db_session) -> None:
    process_demo(db_session)
    item_id = reviewable_item_id(db_session)
    assert item_id is not None
    session = approved_session()
    db_session.add(session)
    db_session.flush()
    db_session.add_all(
        [
            Label(
                item_id=item_id,
                label="true_signal",
                actor_type="human",
                version=1,
                created_at=NOW,
            ),
            Label(
                item_id=item_id,
                label="sensitive_risk",
                actor_type="agent",
                agent_session_id=session.id,
                version=2,
                created_at=NOW + timedelta(seconds=1),
            ),
        ]
    )
    db_session.commit()
    human = get_review_snapshots(db_session, [item_id])
    agent = get_agent_review_snapshots(db_session, [item_id])
    assert unresolved_sensitive_risk(human, agent) is True

    db_session.add(
        Label(
            item_id=item_id,
            label="true_signal",
            actor_type="human",
            version=3,
            created_at=NOW + timedelta(seconds=2),
        )
    )
    db_session.commit()
    human = get_review_snapshots(db_session, [item_id])
    agent = get_agent_review_snapshots(db_session, [item_id])
    assert unresolved_sensitive_risk(human, agent) is False
