"""Append-only agent action audit and idempotency services."""

from app.services.agent_actions.executor import (
    AgentActionExecution,
    execute_audited_agent_action,
)
from app.services.agent_actions.service import (
    CREATE_PROJECT_EXPECTED_VERSION,
    IDEMPOTENCY_CONFLICT,
    IDEMPOTENCY_IN_PROGRESS,
    IDEMPOTENCY_REPLAY,
    INVALID_AGENT_REQUEST,
    INVALID_EXPECTED_VERSION,
    AgentActionServiceError,
    InvalidActionTransition,
    InvalidAgentRequest,
    InvalidExpectedVersion,
    InvalidIdempotencyKey,
    UnsupportedAgentAction,
    canonical_request_hash,
    hash_idempotency_key,
    redacted_agent_action,
    summarize_request,
    summarize_result,
)

__all__ = [
    "AgentActionExecution",
    "CREATE_PROJECT_EXPECTED_VERSION",
    "IDEMPOTENCY_CONFLICT",
    "IDEMPOTENCY_IN_PROGRESS",
    "IDEMPOTENCY_REPLAY",
    "INVALID_AGENT_REQUEST",
    "INVALID_EXPECTED_VERSION",
    "AgentActionServiceError",
    "InvalidActionTransition",
    "InvalidAgentRequest",
    "InvalidExpectedVersion",
    "InvalidIdempotencyKey",
    "UnsupportedAgentAction",
    "canonical_request_hash",
    "execute_audited_agent_action",
    "hash_idempotency_key",
    "redacted_agent_action",
    "summarize_request",
    "summarize_result",
]
