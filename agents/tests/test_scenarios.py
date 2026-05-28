"""
Five end-to-end integration scenarios.
"""
import asyncio
import pytest
from datetime import datetime, timezone, timedelta

from tests.fixtures.gemini_responses import (
    REVIEW_AI_CRITICAL,
    REVIEW_AI_CLEAN,
    TEST_AGENT_CLEAN,
    ROOT_CAUSE_AI_RESPONSE,
)


# ─── Scenario 1: BLOCK path ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scenario_1_critical_pr_blocks_at_review(
    db_service, mock_gemini, mock_event_emitter, mock_github_post, critical_pr_data
):
    from review_agent.agent import run_review

    mock_gemini.queue(REVIEW_AI_CRITICAL)
    report = await run_review(critical_pr_data)

    assert report["decision"] == "BLOCK"
    assert report["summary"]["critical"] >= 1

    approvals = await db_service.list_pending_approvals()
    assert approvals == []


# ─── Scenario 2: AUTO path (clean PR sails through) ──────────────────────────

@pytest.mark.asyncio
async def test_scenario_2_clean_pr_auto_approves_and_deploys(
    db_service, mock_gemini, mock_event_emitter, mock_github_post, clean_pr_data,
    monkeypatch,
):
    from orchestrator.graph import run_pipeline

    mock_gemini.queue(REVIEW_AI_CLEAN)
    mock_gemini.queue(REVIEW_AI_CLEAN)

    from deploy_agent import health_checker

    async def fake_run_all(self):
        return {
            "status": "ok", "passed": True, "checks_run": 3, "checks_passed": 3,
            "checks_failed": 0, "duration_ms": 10,
            "results": [
                {"name": "health_endpoint", "url": "x", "passed": True,
                 "status_code": 200, "latency_ms": 5, "error": None, "attempt": 1},
            ],
        }
    monkeypatch.setattr(health_checker.HealthChecker, "run_all", fake_run_all)
    monkeypatch.setenv("DEPLOY_MONITORING_SECONDS", "1")
    monkeypatch.setenv("DEPLOY_MONITORING_INTERVAL", "1")

    await db_service.save_pipeline(clean_pr_data)
    final_state = await run_pipeline(clean_pr_data)

    # Final pipeline state is AUTO_APPROVE and complete (verified in logs)
    assert final_state.get("final_decision") in ("AUTO_APPROVE", "PROMOTED", "PASS")
    assert final_state.get("status") == "complete"

    # Authoritative check: a deployment record was created and reached promoted
    from boto3.dynamodb.conditions import Key
    result = db_service.deployments_table.query(
        KeyConditionExpression=Key("pipeline_id").eq(clean_pr_data["pipeline_id"]),
    )
    deployments = result.get("Items", [])
    assert len(deployments) == 1, f"Expected 1 deployment record, got {len(deployments)}"
    assert deployments[0]["status"] == "promoted"
    assert deployments[0]["traffic_split"]["green"] == 100


# ─── Scenario 3: SOFT approval, human approves ──────────────────────────────

@pytest.mark.asyncio
async def test_scenario_3_soft_approval_human_approves(db_service):
    risk = {
        "risk_level": "soft", "reason": "Quality concerns",
        "requires_approval": True, "critical_files": [],
    }
    approval_id = await db_service.save_approval_request(
        "pipe_soft_001", risk, {"decision": "REQUEST_CHANGES", "score": 65}
    )
    assert approval_id != ""

    ok = await db_service.transition_approval(
        pipeline_id="pipe_soft_001",
        approval_id=approval_id,
        new_status="approved",
        actor="aryan",
        comment="LGTM",
        expected_status="pending",
    )
    assert ok is True

    approval = await db_service.get_approval("pipe_soft_001", approval_id)
    assert approval["status"] == "approved"
    assert approval["approved_by"] == "aryan"

    # Second attempt fails
    ok2 = await db_service.transition_approval(
        pipeline_id="pipe_soft_001",
        approval_id=approval_id,
        new_status="approved",
        actor="other",
        expected_status="pending",
    )
    assert ok2 is False


# ─── Scenario 4: SOFT auto-promotes after timeout ───────────────────────────

@pytest.mark.asyncio
async def test_scenario_4_soft_approval_auto_promotes_after_timeout(db_service):
    from orchestrator.approval_state_machine import (
        should_auto_promote, ApprovalState, build_event,
    )

    risk = {
        "risk_level": "soft", "reason": "Quality concerns",
        "requires_approval": True, "critical_files": [],
    }
    approval_id = await db_service.save_approval_request(
        "pipe_soft_002", risk, {"decision": "REQUEST_CHANGES"}
    )

    old_ts = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
    db_service.approvals_table.update_item(
        Key={"pipeline_id": "pipe_soft_002", "approval_id": approval_id},
        UpdateExpression="SET created_at = :ts",
        ExpressionAttributeValues={":ts": old_ts},
    )

    approval = await db_service.get_approval("pipe_soft_002", approval_id)
    assert should_auto_promote(approval)

    ok = await db_service.transition_approval(
        pipeline_id="pipe_soft_002",
        approval_id=approval_id,
        new_status=ApprovalState.AUTO_PROMOTED.value,
        actor="system:auto_promote",
        comment="SOFT auto-promoted",
        expected_status="pending",
    )
    assert ok is True
    await db_service.save_approval_event(build_event(
        approval_id=approval_id,
        from_state="pending",
        to_state=ApprovalState.AUTO_PROMOTED.value,
        actor="system:auto_promote",
        comment="Timeout reached",
    ))

    final = await db_service.get_approval("pipe_soft_002", approval_id)
    assert final["status"] == "auto_promoted"

    events = await db_service.list_approval_events(approval_id)
    assert len(events) == 1
    assert events[0]["from_state"] == "pending"
    assert events[0]["to_state"] == "auto_promoted"


# ─── Scenario 5: Incident fires + root cause AI ─────────────────────────────

@pytest.mark.asyncio
async def test_scenario_5_anomaly_fires_incident_with_ai_root_cause(
    db_service, mock_gemini, mock_event_emitter, mock_github_post,
):
    from incident_agent.metric_collector import (
        INJECT_ANOMALY_NEXT, collect_one_sample,
    )
    from incident_agent.agent import evaluate_sample

    DEPLOYMENT_ID = "deploy_test_incident_005"

    await db_service.save_deployment(
        pipeline_id="pipe_incident_005",
        deployment_id=DEPLOYMENT_ID,
        approval_id="",
        repo="test-org/test-repo",
        pr_number=200,
        head_sha="incident123",
    )

    for _ in range(15):
        await collect_one_sample(DEPLOYMENT_ID)

    INJECT_ANOMALY_NEXT["enabled"] = True
    INJECT_ANOMALY_NEXT["spike_factor"] = 12.0
    sample = await collect_one_sample(DEPLOYMENT_ID)

    # evaluate_sample internally fires asyncio.create_task(analyze_root_cause)
    # which consumes one Gemini call. Queue exactly one response.
    mock_gemini.queue(ROOT_CAUSE_AI_RESPONSE)

    incident = await evaluate_sample(DEPLOYMENT_ID, sample)

    assert incident is not None
    assert incident["severity"] in ("warning", "high", "critical")
    assert incident["max_abs_z"] > 3.0

    # Wait for the create_task'd root cause analysis to complete
    # (yield control to the event loop a few times)
    for _ in range(10):
        await asyncio.sleep(0.05)
        incidents = await db_service.list_recent_incidents(DEPLOYMENT_ID, limit=5)
        fired = next((i for i in incidents if i["incident_id"] == incident["incident_id"]), None)
        if fired and fired.get("root_cause"):
            break

    incidents = await db_service.list_recent_incidents(DEPLOYMENT_ID, limit=5)
    fired = next(i for i in incidents if i["incident_id"] == incident["incident_id"])
    assert fired.get("root_cause"), "root_cause should be filled in by AI"
    assert fired["ai_confidence"] == "high"
    assert len(mock_gemini.calls) == 1