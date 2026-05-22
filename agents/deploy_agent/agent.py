"""
DeployAgent — orchestrates blue/green deployments.

Day 13 scope: skeleton + blue slot provisioning + stub smoke test.
Days 14-16 will add real health checks, green slot, traffic shift, rollback.
"""
import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any
from uuid import uuid4

from deploy_agent.deployment_state_machine import (
    DeploymentState,
    build_event,
)
from shared.dynamodb_service import get_dynamodb_service
from shared.logger import get_logger

logger = get_logger(__name__)


async def _transition(db, deployment_id, pipeline_id, from_state, to_state,
                       actor="DeployAgent", comment="", metadata=None):
    """Atomic deployment state transition + audit event."""
    ok = await db.transition_deployment(
        pipeline_id=pipeline_id,
        deployment_id=deployment_id,
        new_status=to_state,
        actor=actor,
        comment=comment,
        expected_status=from_state,
    )
    if ok:
        event = build_event(deployment_id, from_state, to_state, actor, comment, metadata)
        await db.save_deployment_event(event)
    return ok


async def run_deploy(pipeline_data: Dict[str, Any], approval_id: str = None) -> Dict[str, Any]:
    """
    Entry point for DeployAgent.

    Day 13 flow:
        pending -> provisioning -> smoke_test -> ready_for_traffic_shift

    Returns a report dict with deployment_id, final_state, and blue slot info.
    """
    pipeline_id = pipeline_data["pipeline_id"]
    repo = pipeline_data["repo"]
    pr_number = pipeline_data["pr_number"]
    head_sha = pipeline_data["head_sha"]

    deployment_id = f"deploy_{pipeline_id}_{int(time.time())}"
    start_time = time.time()

    logger.info(f"[{pipeline_id}] DeployAgent starting — deployment_id={deployment_id}")

    db = get_dynamodb_service()

    # 1. Create initial deployment record (pending)
    await db.save_deployment(
        pipeline_id=pipeline_id,
        deployment_id=deployment_id,
        approval_id=approval_id,
        repo=repo,
        pr_number=pr_number,
        head_sha=head_sha,
    )
    logger.info(f"[{pipeline_id}] Deployment record created: {deployment_id}")

    try:
        # 2. pending -> provisioning
        blue_slot = {
            "slot_id": f"blue_{uuid4().hex[:8]}",
            "target": "production-blue",
            "image_tag": head_sha[:8],
            "provisioned_at": datetime.now(timezone.utc).isoformat(),
        }
        await _transition(
            db, deployment_id, pipeline_id,
            from_state=DeploymentState.PENDING.value,
            to_state=DeploymentState.PROVISIONING.value,
            comment=f"Provisioning blue slot {blue_slot['slot_id']}",
            metadata={"blue_slot": blue_slot},
        )

        # Simulate provisioning work
        await asyncio.sleep(1)
        logger.info(f"[{pipeline_id}] Blue slot provisioned: {blue_slot['slot_id']}")

        # 3. provisioning -> smoke_test
        await _transition(
            db, deployment_id, pipeline_id,
            from_state=DeploymentState.PROVISIONING.value,
            to_state=DeploymentState.SMOKE_TEST.value,
            comment="Running smoke tests on blue slot",
            metadata={"blue_slot": blue_slot["slot_id"]},
        )

        # 4. Stub smoke test (Day 14 makes this real)
        smoke_result = await _stub_smoke_test(blue_slot)
        logger.info(f"[{pipeline_id}] Smoke test: {smoke_result['status']}")

        if not smoke_result["passed"]:
            # Smoke failed -> failed state
            await _transition(
                db, deployment_id, pipeline_id,
                from_state=DeploymentState.SMOKE_TEST.value,
                to_state=DeploymentState.FAILED.value,
                comment=f"Smoke test failed: {smoke_result['reason']}",
                metadata={"smoke_result": smoke_result},
            )
            duration_ms = int((time.time() - start_time) * 1000)
            return {
                "deployment_id": deployment_id,
                "final_state": DeploymentState.FAILED.value,
                "blue_slot": blue_slot,
                "smoke_result": smoke_result,
                "duration_ms": duration_ms,
                "decision": "DEPLOY_FAILED",
            }

        # 5. smoke_test -> ready_for_traffic_shift (Day 13 stops here)
        await _transition(
            db, deployment_id, pipeline_id,
            from_state=DeploymentState.SMOKE_TEST.value,
            to_state=DeploymentState.READY_FOR_TRAFFIC_SHIFT.value,
            comment="Blue slot verified, ready for green deploy (Day 14+)",
            metadata={"smoke_result": smoke_result},
        )

        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"[{pipeline_id}] DeployAgent complete in {duration_ms}ms — "
            f"state=ready_for_traffic_shift"
        )

        return {
            "deployment_id": deployment_id,
            "final_state": DeploymentState.READY_FOR_TRAFFIC_SHIFT.value,
            "blue_slot": blue_slot,
            "smoke_result": smoke_result,
            "duration_ms": duration_ms,
            "decision": "DEPLOYED_BLUE",
        }

    except Exception as e:
        logger.error(f"[{pipeline_id}] DeployAgent failed: {e}", exc_info=True)
        # Best-effort failure transition (may fail if state already terminal)
        current = await db.get_deployment(pipeline_id, deployment_id)
        if current and not (current.get("status") in ("promoted", "rolled_back", "failed")):
            await _transition(
                db, deployment_id, pipeline_id,
                from_state=current.get("status", "pending"),
                to_state=DeploymentState.FAILED.value,
                comment=f"Unexpected error: {str(e)[:200]}",
            )
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "deployment_id": deployment_id,
            "final_state": DeploymentState.FAILED.value,
            "error": str(e),
            "duration_ms": duration_ms,
            "decision": "DEPLOY_FAILED",
        }


async def _stub_smoke_test(blue_slot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Day 13 stub: pretends to run a smoke test.
    Day 14 replaces this with real HTTP health checks.
    """
    await asyncio.sleep(0.5)
    return {
        "status": "ok",
        "passed": True,
        "checks_run": 3,
        "checks_passed": 3,
        "duration_ms": 500,
        "slot_id": blue_slot["slot_id"],
    }