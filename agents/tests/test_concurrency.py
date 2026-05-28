"""
Day 25 — concurrency and edge case tests.

These exercise the conditional-write race condition prevention,
terminal state enforcement, cooldown gating, and state recoverability.
"""
import asyncio
import pytest
from datetime import datetime, timezone, timedelta

from tests.fixtures.gemini_responses import ROOT_CAUSE_AI_RESPONSE


# ─── Test 1: Concurrent approves — exactly one wins ──────────────────────────

@pytest.mark.asyncio
async def test_concurrent_approve_calls_only_one_wins(db_service):
    """
    Two approves fired at the same instant. Conditional update ensures
    exactly one transitions pending->approved; the other gets False.
    """
    risk = {
        "risk_level": "soft", "reason": "Quality concerns",
        "requires_approval": True, "critical_files": [],
    }
    approval_id = await db_service.save_approval_request(
        "pipe_race_001", risk, {"decision": "REQUEST_CHANGES"}
    )

    # Fire two approves concurrently
    results = await asyncio.gather(
        db_service.transition_approval(
            pipeline_id="pipe_race_001",
            approval_id=approval_id,
            new_status="approved",
            actor="alice",
            comment="LGTM",
            expected_status="pending",
        ),
        db_service.transition_approval(
            pipeline_id="pipe_race_001",
            approval_id=approval_id,
            new_status="approved",
            actor="bob",
            comment="Also LGTM",
            expected_status="pending",
        ),
    )

    # Exactly one True, exactly one False
    assert sum(results) == 1, f"Expected exactly one winner, got {results}"

    # Final state is approved; only one actor wrote
    final = await db_service.get_approval("pipe_race_001", approval_id)
    assert final["status"] == "approved"
    assert final["approved_by"] in ("alice", "bob")


# ─── Test 2: Reject on terminal state fails ──────────────────────────────────

@pytest.mark.asyncio
async def test_reject_after_approve_is_refused(db_service):
    """
    Approve an approval (terminal). Try to reject. State machine refuses
    because the conditional update's expected_status='pending' no longer matches.
    """
    risk = {
        "risk_level": "soft", "reason": "Standard PR",
        "requires_approval": True, "critical_files": [],
    }
    approval_id = await db_service.save_approval_request(
        "pipe_terminal_001", risk, {"decision": "REQUEST_CHANGES"}
    )

    ok_approve = await db_service.transition_approval(
        pipeline_id="pipe_terminal_001",
        approval_id=approval_id,
        new_status="approved",
        actor="alice",
        expected_status="pending",
    )
    assert ok_approve is True

    # Try to reject (still expecting pending). Must fail.
    ok_reject = await db_service.transition_approval(
        pipeline_id="pipe_terminal_001",
        approval_id=approval_id,
        new_status="rejected",
        actor="bob",
        expected_status="pending",
    )
    assert ok_reject is False, "Cannot reject an already-approved approval"

    # State unchanged
    final = await db_service.get_approval("pipe_terminal_001", approval_id)
    assert final["status"] == "approved"
    assert final["approved_by"] == "alice"


# ─── Test 3: Worker auto-promote vs human approve race ───────────────────────

@pytest.mark.asyncio
async def test_auto_promote_vs_human_approve_race(db_service):
    """
    Worker fires auto_promoted at the same instant a human fires approved.
    Both target expected_status='pending'. Exactly one wins.
    """
    risk = {
        "risk_level": "soft", "reason": "Standard PR",
        "requires_approval": True, "critical_files": [],
    }
    approval_id = await db_service.save_approval_request(
        "pipe_race_003", risk, {"decision": "REQUEST_CHANGES"}
    )

    results = await asyncio.gather(
        # The worker
        db_service.transition_approval(
            pipeline_id="pipe_race_003",
            approval_id=approval_id,
            new_status="auto_promoted",
            actor="system:auto_promote",
            expected_status="pending",
        ),
        # The human, racing the worker
        db_service.transition_approval(
            pipeline_id="pipe_race_003",
            approval_id=approval_id,
            new_status="approved",
            actor="aryan",
            expected_status="pending",
        ),
    )

    # Exactly one transition succeeded
    assert sum(results) == 1, f"Expected exactly one winner, got {results}"

    # Final state is one of the two terminal values
    final = await db_service.get_approval("pipe_race_003", approval_id)
    assert final["status"] in ("approved", "auto_promoted")


# ─── Test 4: Incident cooldown suppresses duplicate fires ────────────────────

@pytest.mark.asyncio
async def test_incident_cooldown_suppresses_duplicate(
    db_service, mock_gemini, mock_event_emitter, mock_github_post,
):
    """
    Fire an anomaly, then fire another within the cooldown window.
    The second must be suppressed.
    """
    from incident_agent.metric_collector import (
        INJECT_ANOMALY_NEXT, collect_one_sample,
    )
    from incident_agent.agent import evaluate_sample

    DEPLOYMENT_ID = "deploy_cooldown_004"

    await db_service.save_deployment(
        pipeline_id="pipe_cooldown_004",
        deployment_id=DEPLOYMENT_ID,
        approval_id="",
        repo="test-org/test-repo",
        pr_number=300,
        head_sha="cooldown123",
    )

    # Healthy baseline
    for _ in range(15):
        await collect_one_sample(DEPLOYMENT_ID)

    # AI response for the first incident's create_task'd root cause analysis
    mock_gemini.queue(ROOT_CAUSE_AI_RESPONSE)

    # First anomaly - fires
    INJECT_ANOMALY_NEXT["enabled"] = True
    INJECT_ANOMALY_NEXT["spike_factor"] = 12.0
    sample_1 = await collect_one_sample(DEPLOYMENT_ID)
    incident_1 = await evaluate_sample(DEPLOYMENT_ID, sample_1)
    assert incident_1 is not None, "First anomaly must fire"

    # Wait for the create_task to finish (so it doesn't consume a future Gemini response)
    for _ in range(10):
        await asyncio.sleep(0.05)
        if len(mock_gemini.calls) >= 1:
            break

    # Second anomaly within cooldown window - suppressed
    INJECT_ANOMALY_NEXT["enabled"] = True
    INJECT_ANOMALY_NEXT["spike_factor"] = 12.0
    sample_2 = await collect_one_sample(DEPLOYMENT_ID)
    incident_2 = await evaluate_sample(DEPLOYMENT_ID, sample_2)
    assert incident_2 is None, "Second anomaly must be suppressed by cooldown"

    # Only one incident exists in DynamoDB
    incidents = await db_service.list_recent_incidents(DEPLOYMENT_ID, limit=5)
    assert len(incidents) == 1


# ─── Test 5: State recovery after simulated restart ──────────────────────────

@pytest.mark.asyncio
async def test_state_recoverable_after_simulated_restart(aws_mock):
    """
    Simulate a container restart by recreating the DynamoDBService singleton.
    State written by the 'old' service must be readable by the 'new' service.

    This proves there's no in-memory state required to resume operations —
    everything sits in DynamoDB.
    """
    import shared.dynamodb_service as ds

    # First "process": write a deployment record mid-traffic-shift
    ds._service = None
    old_service = ds.get_dynamodb_service()
    await old_service.save_deployment(
        pipeline_id="pipe_restart_005",
        deployment_id="deploy_restart_005",
        approval_id="",
        repo="test-org/test-repo",
        pr_number=500,
        head_sha="restart123",
    )
    await old_service.transition_deployment(
        pipeline_id="pipe_restart_005",
        deployment_id="deploy_restart_005",
        new_status="traffic_shifting",
        actor="DeployAgent",
        comment="Mid-shift, container about to die",
        expected_status="pending",
    )
    await old_service.update_deployment_traffic_split(
        pipeline_id="pipe_restart_005",
        deployment_id="deploy_restart_005",
        blue_percent=50,
        green_percent=50,
    )

    # Simulate restart: wipe the singleton, get a fresh service instance
    ds._service = None
    new_service = ds.get_dynamodb_service()
    assert new_service is not old_service, "Singleton should be a new instance"

    # New service can read the state the old one left behind
    deployment = await new_service.get_deployment(
        "pipe_restart_005", "deploy_restart_005"
    )
    assert deployment is not None
    assert deployment["status"] == "traffic_shifting"
    assert deployment["traffic_split"]["blue"] == 50
    assert deployment["traffic_split"]["green"] == 50

    # The state machine knows we're at traffic_shifting, so resume logic can
    # decide: continue shift, or check health and possibly rollback. Either way,
    # no in-memory state needed.