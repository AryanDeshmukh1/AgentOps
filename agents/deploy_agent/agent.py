"""
DeployAgent — orchestrates blue/green deployments.

Day 16 scope:
    pending -> provisioning -> smoke_test -> ready_for_traffic_shift
            -> traffic_shifting (10/50/100) -> monitoring -> promoted

    On traffic_shifting or monitoring failure: auto-rollback to 100% blue,
    transition to rolled_back, and notify the PR.
"""
import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Dict, Any
from uuid import uuid4


from deploy_agent.deployment_state_machine import DeploymentState, build_event
from deploy_agent.health_checker import HealthChecker, default_checks_for_target
from deploy_agent.traffic_shifter import TrafficShifter, monitoring_window
from shared.dynamodb_service import get_dynamodb_service
from shared.logger import get_logger
from deploy_agent.rollback import (
    execute_rollback,
    extract_failure_context_from_shift,
    extract_failure_context_from_monitor,
)


logger = get_logger(__name__)


async def _transition(db, deployment_id, pipeline_id, from_state, to_state,
                       actor="DeployAgent", comment="", metadata=None):
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


def _build_slot(color: str, head_sha: str) -> Dict[str, Any]:
    return {
        "slot_id": f"{color}_{uuid4().hex[:8]}",
        "color": color,
        "target": f"production-{color}",
        "image_tag": head_sha[:8] if head_sha else "unknown",
        "provisioned_at": datetime.now(timezone.utc).isoformat(),
    }


async def run_deploy(pipeline_data: Dict[str, Any], approval_id: str = None) -> Dict[str, Any]:
    pipeline_id = pipeline_data["pipeline_id"]
    repo = pipeline_data["repo"]
    pr_number = pipeline_data["pr_number"]
    head_sha = pipeline_data["head_sha"]

    deployment_id = f"deploy_{pipeline_id}_{int(time.time())}"
    start_time = time.time()

    health_check_base_url = os.getenv("DEPLOY_HEALTH_CHECK_URL", "http://backend:4000")
    monitoring_seconds = int(os.getenv("DEPLOY_MONITORING_SECONDS", "10"))
    monitoring_interval = int(os.getenv("DEPLOY_MONITORING_INTERVAL", "5"))

    logger.info(
        f"[{pipeline_id}] DeployAgent starting — deployment_id={deployment_id}, "
        f"health_target={health_check_base_url}, monitor={monitoring_seconds}s"
    )

    db = get_dynamodb_service()

    await db.save_deployment(
        pipeline_id=pipeline_id, deployment_id=deployment_id,
        approval_id=approval_id, repo=repo, pr_number=pr_number, head_sha=head_sha,
    )

    try:
        # === PROVISIONING ===
        blue_slot = _build_slot("blue", head_sha)
        green_slot = _build_slot("green", head_sha)

        await _transition(
            db, deployment_id, pipeline_id,
            from_state=DeploymentState.PENDING.value,
            to_state=DeploymentState.PROVISIONING.value,
            comment=f"Provisioning blue={blue_slot['slot_id']}, green={green_slot['slot_id']}",
            metadata={"blue_slot": blue_slot, "green_slot": green_slot},
        )
        await asyncio.sleep(1)

        # === SMOKE TEST ===
        await _transition(
            db, deployment_id, pipeline_id,
            from_state=DeploymentState.PROVISIONING.value,
            to_state=DeploymentState.SMOKE_TEST.value,
            comment=f"Health checks against green {green_slot['slot_id']}",
        )

        checks = default_checks_for_target(health_check_base_url)
        smoke_checker = HealthChecker(checks=checks, max_retries=3)
        smoke_result = await smoke_checker.run_all()
        smoke_result["slot_id"] = green_slot["slot_id"]

        # Smoke failure -> FAILED (no rollback, no traffic was shifted)
        if not smoke_result["passed"]:
            await _transition(
                db, deployment_id, pipeline_id,
                from_state=DeploymentState.SMOKE_TEST.value,
                to_state=DeploymentState.FAILED.value,
                comment=f"Smoke failed: {smoke_result['checks_failed']} check(s)",
                metadata={"smoke_result": smoke_result},
            )
            return _result(deployment_id, "failed", blue_slot, green_slot,
                          smoke_result, None, None, start_time, "DEPLOY_FAILED")

        # === READY FOR TRAFFIC SHIFT ===
        await _transition(
            db, deployment_id, pipeline_id,
            from_state=DeploymentState.SMOKE_TEST.value,
            to_state=DeploymentState.READY_FOR_TRAFFIC_SHIFT.value,
            comment=f"Green healthy ({smoke_result['checks_passed']}/{smoke_result['checks_run']})",
            metadata={"smoke_result": smoke_result},
        )

        # === TRAFFIC SHIFTING ===
        await _transition(
            db, deployment_id, pipeline_id,
            from_state=DeploymentState.READY_FOR_TRAFFIC_SHIFT.value,
            to_state=DeploymentState.TRAFFIC_SHIFTING.value,
            comment="Starting gradual traffic shift",
        )

        async def persist_split(blue_pct, green_pct):
            await db.update_deployment_traffic_split(
                pipeline_id, deployment_id, blue_pct, green_pct
            )

        shift_checker = HealthChecker(checks=checks, max_retries=2)
        shifter = TrafficShifter(
            health_checker=shift_checker,
            on_shift=persist_split,
        )
        shift_result = await shifter.run()

        # Traffic-shift failure -> ROLLBACK (revert traffic to blue)
        if not shift_result["passed"]:
            failure_ctx = extract_failure_context_from_shift(shift_result)
            failure_ctx["head_sha"] = head_sha
            rollback_outcome = await execute_rollback(
                db=db,
                pipeline_id=pipeline_id,
                deployment_id=deployment_id,
                repo=repo,
                pr_number=pr_number,
                from_state=DeploymentState.TRAFFIC_SHIFTING.value,
                reason=shift_result["halt_reason"],
                failure_context=failure_ctx,
            )
            return _result(deployment_id, "rolled_back", blue_slot, green_slot,
                          smoke_result, shift_result, None, start_time,
                          "ROLLED_BACK_IN_TRAFFIC_SHIFT",
                          extra={"rollback": rollback_outcome})

        # === MONITORING WINDOW ===
        await _transition(
            db, deployment_id, pipeline_id,
            from_state=DeploymentState.TRAFFIC_SHIFTING.value,
            to_state=DeploymentState.MONITORING.value,
            comment=f"100% green — monitoring for {monitoring_seconds}s",
            metadata={"shift_result": shift_result},
        )

        monitor_checker = HealthChecker(checks=checks, max_retries=2)
        monitor_result = await monitoring_window(
            health_checker=monitor_checker,
            duration_seconds=monitoring_seconds,
            interval_seconds=monitoring_interval,
        )

        # Monitoring failure -> ROLLBACK (revert traffic to blue)
        if not monitor_result["passed"]:
            failure_ctx = extract_failure_context_from_monitor(monitor_result)
            failure_ctx["head_sha"] = head_sha
            rollback_outcome = await execute_rollback(
                db=db,
                pipeline_id=pipeline_id,
                deployment_id=deployment_id,
                repo=repo,
                pr_number=pr_number,
                from_state=DeploymentState.MONITORING.value,
                reason=f"Health degraded {monitor_result['duration_seconds']}s into monitoring window",
                failure_context=failure_ctx,
            )
            return _result(deployment_id, "rolled_back", blue_slot, green_slot,
                          smoke_result, shift_result, monitor_result,
                          start_time, "ROLLED_BACK_IN_MONITORING",
                          extra={"rollback": rollback_outcome})

        # === PROMOTED ===
        await _transition(
            db, deployment_id, pipeline_id,
            from_state=DeploymentState.MONITORING.value,
            to_state=DeploymentState.PROMOTED.value,
            comment=f"Promoted after {monitor_result['duration_seconds']}s stable monitoring",
            metadata={"monitor_result": monitor_result},
        )

        return _result(deployment_id, "promoted", blue_slot, green_slot,
                      smoke_result, shift_result, monitor_result,
                      start_time, "PROMOTED")

    except Exception as e:
        logger.error(f"[{pipeline_id}] DeployAgent failed: {e}", exc_info=True)
        current = await db.get_deployment(pipeline_id, deployment_id)
        if current and current.get("status") not in ("promoted", "rolled_back", "failed"):
            await _transition(
                db, deployment_id, pipeline_id,
                from_state=current.get("status", "pending"),
                to_state=DeploymentState.FAILED.value,
                comment=f"Unexpected error: {str(e)[:200]}",
            )
        return _result(deployment_id, "failed", None, None, None, None, None,
                      start_time, "DEPLOY_FAILED", error=str(e))


def _result(deployment_id, final_state, blue_slot, green_slot, smoke,
            shift, monitor, start_time, decision, error=None, extra=None):
    result = {
        "deployment_id": deployment_id,
        "final_state": final_state,
        "blue_slot": blue_slot,
        "green_slot": green_slot,
        "smoke_result": smoke,
        "shift_result": shift,
        "monitor_result": monitor,
        "duration_ms": int((time.time() - start_time) * 1000),
        "decision": decision,
        "error": error,
    }
    if extra:
        result.update(extra)
    return result