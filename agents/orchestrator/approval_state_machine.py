"""
Approval State Machine.

States:
  pending        -> initial state after risk classifier creates approval
  approved       -> human approved via API
  rejected       -> human rejected via API
  auto_promoted  -> SOFT approval timed out and auto-promoted
  expired        -> HARD approval timed out, no decision made

Valid transitions:
  pending -> approved | rejected | auto_promoted | expired

Terminal states: approved, rejected, auto_promoted, expired
"""
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, Optional, Tuple


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    AUTO_PROMOTED = "auto_promoted"
    EXPIRED = "expired"


TERMINAL_STATES = {
    ApprovalState.APPROVED,
    ApprovalState.REJECTED,
    ApprovalState.AUTO_PROMOTED,
    ApprovalState.EXPIRED,
}

VALID_TRANSITIONS = {
    ApprovalState.PENDING: {
        ApprovalState.APPROVED,
        ApprovalState.REJECTED,
        ApprovalState.AUTO_PROMOTED,
        ApprovalState.EXPIRED,
    },
}

SOFT_AUTO_PROMOTE_MINUTES = 30
HARD_EXPIRE_HOURS = 24


def can_transition(from_state: str, to_state: str) -> bool:
    try:
        from_s = ApprovalState(from_state)
        to_s = ApprovalState(to_state)
    except ValueError:
        return False
    return to_s in VALID_TRANSITIONS.get(from_s, set())


def is_terminal(state: str) -> bool:
    try:
        return ApprovalState(state) in TERMINAL_STATES
    except ValueError:
        return False


def should_auto_promote(approval: Dict[str, Any]) -> bool:
    if approval.get("status") != ApprovalState.PENDING.value:
        return False
    if approval.get("risk_level") != "soft":
        return False
    created_at = approval.get("created_at")
    if not created_at:
        return False
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - created
    return age >= timedelta(minutes=SOFT_AUTO_PROMOTE_MINUTES)


def should_expire(approval: Dict[str, Any]) -> bool:
    if approval.get("status") != ApprovalState.PENDING.value:
        return False
    if approval.get("risk_level") != "hard":
        return False
    created_at = approval.get("created_at")
    if not created_at:
        return False
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - created
    return age >= timedelta(hours=HARD_EXPIRE_HOURS)


def build_event(
    approval_id: str,
    from_state: str,
    to_state: str,
    actor: str,
    comment: str = "",
) -> Dict[str, Any]:
    return {
        "approval_id": approval_id,
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "from_state": from_state,
        "to_state": to_state,
        "actor": actor,
        "comment": comment,
    }


def validate_transition(
    current_state: str,
    new_state: str,
) -> Tuple[bool, Optional[str]]:
    if is_terminal(current_state):
        return False, f"Approval is already in terminal state '{current_state}'"
    if not can_transition(current_state, new_state):
        return False, f"Invalid transition from '{current_state}' to '{new_state}'"
    return True, None