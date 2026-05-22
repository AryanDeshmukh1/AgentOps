"""
Deployment State Machine.

States:
  pending                    -> initial state after creation
  provisioning               -> blue slot being set up
  smoke_test                 -> running smoke tests against blue
  ready_for_traffic_shift    -> blue verified, ready for green deploy (Day 14+)
  traffic_shifting           -> gradual traffic migration (Day 15)
  monitoring                 -> watching metrics post-shift (Day 15)
  promoted                   -> deployment succeeded
  rolled_back                -> deployment failed and reverted (Day 16)
  failed                     -> deployment errored out unrecoverably

Valid transitions:
  pending             -> provisioning | failed
  provisioning        -> smoke_test | failed
  smoke_test          -> ready_for_traffic_shift | failed
  ready_for_traffic_shift -> traffic_shifting | failed
  traffic_shifting    -> monitoring | rolled_back | failed
  monitoring          -> promoted | rolled_back

Terminal states: promoted, rolled_back, failed
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, Tuple


class DeploymentState(str, Enum):
    PENDING = "pending"
    PROVISIONING = "provisioning"
    SMOKE_TEST = "smoke_test"
    READY_FOR_TRAFFIC_SHIFT = "ready_for_traffic_shift"
    TRAFFIC_SHIFTING = "traffic_shifting"
    MONITORING = "monitoring"
    PROMOTED = "promoted"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


TERMINAL_STATES = {
    DeploymentState.PROMOTED,
    DeploymentState.ROLLED_BACK,
    DeploymentState.FAILED,
}

VALID_TRANSITIONS = {
    DeploymentState.PENDING: {DeploymentState.PROVISIONING, DeploymentState.FAILED},
    DeploymentState.PROVISIONING: {DeploymentState.SMOKE_TEST, DeploymentState.FAILED},
    DeploymentState.SMOKE_TEST: {DeploymentState.READY_FOR_TRAFFIC_SHIFT, DeploymentState.FAILED},
    DeploymentState.READY_FOR_TRAFFIC_SHIFT: {DeploymentState.TRAFFIC_SHIFTING, DeploymentState.FAILED},
    DeploymentState.TRAFFIC_SHIFTING: {DeploymentState.MONITORING, DeploymentState.ROLLED_BACK, DeploymentState.FAILED},
    DeploymentState.MONITORING: {DeploymentState.PROMOTED, DeploymentState.ROLLED_BACK},
}


def can_transition(from_state: str, to_state: str) -> bool:
    try:
        from_s = DeploymentState(from_state)
        to_s = DeploymentState(to_state)
    except ValueError:
        return False
    return to_s in VALID_TRANSITIONS.get(from_s, set())


def is_terminal(state: str) -> bool:
    try:
        return DeploymentState(state) in TERMINAL_STATES
    except ValueError:
        return False


def validate_transition(current_state: str, new_state: str) -> Tuple[bool, Optional[str]]:
    if is_terminal(current_state):
        return False, f"Deployment is in terminal state '{current_state}'"
    if not can_transition(current_state, new_state):
        return False, f"Invalid transition from '{current_state}' to '{new_state}'"
    return True, None


def build_event(
    deployment_id: str,
    from_state: str,
    to_state: str,
    actor: str,
    comment: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "deployment_id": deployment_id,
        "event_timestamp": datetime.now(timezone.utc).isoformat(),
        "from_state": from_state,
        "to_state": to_state,
        "actor": actor,
        "comment": comment,
        "metadata": metadata or {},
    }