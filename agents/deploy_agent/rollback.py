"""
Rollback handler — reverts traffic to 100% blue and notifies stakeholders.

Used by DeployAgent when:
  - Health checks fail during traffic_shifting
  - Health degrades during the monitoring window
  - A human triggers manual rollback via the backend API
"""
import os
from typing import Dict, Any, Optional
import httpx

from deploy_agent.deployment_state_machine import DeploymentState, build_event
from shared.logger import get_logger

logger = get_logger(__name__)


async def execute_rollback(
    db,
    pipeline_id: str,
    deployment_id: str,
    repo: str,
    pr_number: int,
    from_state: str,
    reason: str,
    failure_context: Dict[str, Any],
    actor: str = "DeployAgent",
) -> Dict[str, Any]:
    """
    Revert traffic to 100% blue, transition state to rolled_back, persist audit,
    and notify the originating PR via GitHub.

    Returns a result dict with rollback outcome.
    """
    logger.info(
        f"[{pipeline_id}] Rollback initiated: from {from_state}, reason: {reason}"
    )

    # 1. Revert the traffic split
    await db.update_deployment_traffic_split(
        pipeline_id=pipeline_id,
        deployment_id=deployment_id,
        blue_percent=100,
        green_percent=0,
    )
    logger.info(f"[{pipeline_id}] Traffic reverted to blue=100% / green=0%")

    # 2. State transition (from_state -> rolled_back)
    ok = await db.transition_deployment(
        pipeline_id=pipeline_id,
        deployment_id=deployment_id,
        new_status=DeploymentState.ROLLED_BACK.value,
        actor=actor,
        comment=f"Auto-rollback: {reason}",
        expected_status=from_state,
    )

    if not ok:
        logger.warning(
            f"[{pipeline_id}] Rollback state transition rejected — "
            f"deployment may already be in terminal state"
        )

    # 3. Audit event with full failure context
    event = build_event(
        deployment_id=deployment_id,
        from_state=from_state,
        to_state=DeploymentState.ROLLED_BACK.value,
        actor=actor,
        comment=f"Rollback: {reason}",
        metadata={
            "rollback_reason": reason,
            "failure_context": failure_context,
            "traffic_reverted_to": {"blue": 100, "green": 0},
        },
    )
    await db.save_deployment_event(event)

    # 4. Notify the PR via GitHub
    github_notified = await _notify_github_pr(
        repo=repo,
        pr_number=pr_number,
        deployment_id=deployment_id,
        reason=reason,
        failure_context=failure_context,
    )

    return {
        "rolled_back": True,
        "traffic_reverted_to": {"blue": 100, "green": 0},
        "reason": reason,
        "github_notified": github_notified,
    }


async def _notify_github_pr(
    repo: str,
    pr_number: int,
    deployment_id: str,
    reason: str,
    failure_context: Dict[str, Any],
) -> bool:
    """Post a rollback notification comment to the PR via the backend webhook."""
    backend_url = os.getenv("BACKEND_URL", "http://backend:4000")
    comment = _format_rollback_comment(deployment_id, reason, failure_context)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{backend_url}/api/webhooks/post-review",
                json={
                    "repo": repo,
                    "pr_number": pr_number,
                    "comment": comment,
                    "head_sha": failure_context.get("head_sha", ""),
                    "decision": "ROLLED_BACK",
                },
            )
            if response.status_code == 200:
                logger.info(f"[{deployment_id}] Rollback notification posted to PR #{pr_number}")
                return True
            logger.warning(
                f"[{deployment_id}] Rollback notification HTTP {response.status_code}"
            )
            return False
    except Exception as e:
        logger.error(f"[{deployment_id}] Rollback notification failed: {e}")
        return False


def _format_rollback_comment(deployment_id: str, reason: str, ctx: Dict[str, Any]) -> str:
    """Build a markdown-formatted GitHub comment explaining the rollback."""
    lines = [
        "## 🔴 Deployment Rolled Back",
        "",
        f"**Deployment ID:** `{deployment_id}`",
        f"**Reason:** {reason}",
        "",
        "### What happened",
        f"Traffic was being shifted to the new (green) deployment when health checks failed. "
        f"All traffic has been automatically reverted to the previous (blue) deployment. "
        f"Production is stable.",
        "",
    ]

    # Health check failure details
    failed_checks = ctx.get("failed_checks", [])
    if failed_checks:
        lines.append("### Failed checks")
        for check in failed_checks[:5]:  # cap at 5 to keep comment readable
            lines.append(
                f"- `{check.get('name', 'unknown')}` → "
                f"{check.get('error', 'no error message')}"
            )
        lines.append("")

    # Traffic state at failure
    traffic_at_failure = ctx.get("traffic_at_failure")
    if traffic_at_failure:
        lines.append(
            f"### Traffic state at failure\n"
            f"`blue={traffic_at_failure.get('blue', '?')}% / "
            f"green={traffic_at_failure.get('green', '?')}%`"
        )
        lines.append("")

    lines.append("### Next steps")
    lines.append("- Review the failure context above")
    lines.append("- Fix the underlying issue")
    lines.append("- Push a new commit to trigger a fresh deployment")
    lines.append("")
    lines.append("*Auto-generated by AgentOps DeployAgent.*")

    return "\n".join(lines)


def extract_failure_context_from_shift(shift_result: Dict[str, Any]) -> Dict[str, Any]:
    """Pull useful failure details from a halted traffic_shift result."""
    failed_checks = []
    traffic_at_failure = {}

    for step in shift_result.get("step_results", []):
        if not step.get("health_passed", True):
            traffic_at_failure = {
                "blue": step["blue_percent"],
                "green": step["green_percent"],
            }
            for check_result in step.get("health_summary", {}).get("results", []):
                if not check_result.get("passed", True):
                    failed_checks.append({
                        "name": check_result.get("name"),
                        "url": check_result.get("url"),
                        "error": check_result.get("error"),
                        "status_code": check_result.get("status_code"),
                    })
            break

    return {
        "phase": "traffic_shifting",
        "halt_reason": shift_result.get("halt_reason", ""),
        "failed_checks": failed_checks,
        "traffic_at_failure": traffic_at_failure,
        "steps_completed": shift_result.get("steps_completed"),
        "steps_total": shift_result.get("steps_total"),
    }


def extract_failure_context_from_monitor(monitor_result: Dict[str, Any]) -> Dict[str, Any]:
    """Pull useful failure details from a degraded monitoring_window result."""
    failed_checks = []
    failures = monitor_result.get("failures", [])

    if failures:
        first_failure = failures[0]
        for check_result in first_failure.get("summary", {}).get("results", []):
            if not check_result.get("passed", True):
                failed_checks.append({
                    "name": check_result.get("name"),
                    "url": check_result.get("url"),
                    "error": check_result.get("error"),
                    "status_code": check_result.get("status_code"),
                })

    return {
        "phase": "monitoring",
        "failed_checks": failed_checks,
        "traffic_at_failure": {"blue": 0, "green": 100},
        "elapsed_seconds": monitor_result.get("duration_seconds"),
        "checks_run": monitor_result.get("checks_run"),
        "checks_passed": monitor_result.get("checks_passed"),
    }