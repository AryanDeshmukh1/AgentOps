/**
 * JS mirror of agents/orchestrator/approval_state_machine.py
 */

export const STATES = {
  PENDING: "pending",
  APPROVED: "approved",
  REJECTED: "rejected",
  AUTO_PROMOTED: "auto_promoted",
  EXPIRED: "expired",
};

const TERMINAL_STATES = new Set([
  STATES.APPROVED,
  STATES.REJECTED,
  STATES.AUTO_PROMOTED,
  STATES.EXPIRED,
]);

const VALID_TRANSITIONS = {
  [STATES.PENDING]: new Set([
    STATES.APPROVED,
    STATES.REJECTED,
    STATES.AUTO_PROMOTED,
    STATES.EXPIRED,
  ]),
};

export function isTerminal(state) {
  return TERMINAL_STATES.has(state);
}

export function canTransition(fromState, toState) {
  return VALID_TRANSITIONS[fromState]?.has(toState) ?? false;
}

export function validateTransition(currentState, newState) {
  if (isTerminal(currentState)) {
    return { ok: false, error: `Approval is already in terminal state '${currentState}'` };
  }
  if (!canTransition(currentState, newState)) {
    return { ok: false, error: `Invalid transition from '${currentState}' to '${newState}'` };
  }
  return { ok: true };
}

export function buildEvent(approvalId, fromState, toState, actor, comment = "") {
  return {
    approval_id: approvalId,
    event_timestamp: new Date().toISOString(),
    from_state: fromState,
    to_state: toState,
    actor,
    comment,
  };
}