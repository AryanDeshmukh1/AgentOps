"""
Root Cause AI — gathers context for an incident and asks Gemini what likely caused it.

Flow:
  1. Gather context (deployment record, agent decisions, anomaly details)
  2. Build a structured prompt
  3. Call Gemini with JSON response mode
  4. Save root_cause + suggested_fix + confidence to the incident record
  5. Post a summary comment to the originating PR
"""
import os
import json
from typing import Dict, Any, Optional
import httpx

from shared.dynamodb_service import get_dynamodb_service, _restore_decimals
from shared.gemini_client import get_gemini_client
from shared.logger import get_logger
from shared.event_emitter import emit_event, Channels

logger = get_logger(__name__)


SYSTEM_PROMPT_TEMPLATE = """You are a senior site reliability engineer analyzing a production incident.

A deployment was promoted to 100% traffic, and an anomaly detector then flagged metric regressions
beyond 3 standard deviations from the rolling baseline. Your job: given the context below, hypothesize
the most likely root cause and recommend a concrete next step.

## Incident summary
- Deployment ID: {deployment_id}
- Severity: {severity}
- Max |z-score|: {max_abs_z}
- Triggering metrics:
{triggers_block}

## Baseline (rolling window of recent samples)
{baseline_block}

## Current sample (the one that fired the alert)
{sample_block}

## Recent deployment context
- Repo: {repo}
- PR #{pr_number}
- Commit SHA: {head_sha}
- Promoted at: {promoted_at}

## Recent agent decisions on this PR
{agent_decisions_block}

## Your task
Return STRICT JSON with these fields:
- "root_cause": a 1-2 sentence hypothesis for what most likely caused this regression
- "suggested_fix": a concrete next step (e.g., "review the new database query in src/payments/processor.py" or "rollback and investigate")
- "confidence": one of "high", "medium", "low"
- "investigation_hints": array of 2-4 specific files or systems to investigate

Be specific. Tie your hypothesis to the metrics that fired. If the data is ambiguous, say so and set confidence to "low".
"""


def _format_triggers(anomalous_metrics: list) -> str:
    if not anomalous_metrics:
        return "  (none)"
    lines = []
    for m in anomalous_metrics:
        lines.append(
            f"  - {m['name']}: current={m['current_value']}, "
            f"baseline_mean={m['baseline_mean']}, z={m['z_score']:+.2f} "
            f"({m['direction']}-spike)"
        )
    return "\n".join(lines)


def _format_baseline(baseline_snapshot: Dict[str, Any]) -> str:
    metrics = baseline_snapshot.get("metrics", {})
    lines = [f"  Sample count: {baseline_snapshot.get('sample_count', '?')}"]
    for name, stats in metrics.items():
        lines.append(
            f"  {name}: mean={stats['mean']}, stddev={stats['stddev']}, "
            f"min={stats['min']}, max={stats['max']}, n={stats['n']}"
        )
    return "\n".join(lines)


def _format_sample(sample: Dict[str, Any]) -> str:
    return (
        f"  error_rate_pct: {sample.get('error_rate_pct')}\n"
        f"  latency_p95_ms: {sample.get('latency_p95_ms')}\n"
        f"  request_volume_rpm: {sample.get('request_volume_rpm')}\n"
        f"  collected_at: {sample.get('metric_timestamp')}"
    )


def _format_agent_decisions(decisions: list) -> str:
    if not decisions:
        return "  (no prior agent decisions found for this pipeline)"
    lines = []
    for d in decisions[:5]:
        agent = d.get("agent_name", "?")
        report = d.get("report", {})
        decision = report.get("decision", "?")
        score = report.get("scores", {}).get("overall", "?")
        lines.append(f"  - {agent}: decision={decision}, score={score}")
    return "\n".join(lines)


async def _find_deployment_by_id(db, deployment_id: str) -> Optional[Dict[str, Any]]:
    """Scan deployments table for a given deployment_id (rare call, used only on incident fire)."""
    try:
        result = db.deployments_table.scan(
            FilterExpression="deployment_id = :did",
            ExpressionAttributeValues={":did": deployment_id},
            Limit=1,
        )
        items = _restore_decimals(result.get("Items", []))
        return items[0] if items else None
    except Exception as e:
        logger.error(f"Failed to find deployment: {e}")
        return None


async def _gather_context(incident: Dict[str, Any]) -> Dict[str, Any]:
    """Pull all the context needed for the Gemini prompt."""
    db = get_dynamodb_service()
    deployment_id = incident["deployment_id"]

    deployment = await _find_deployment_by_id(db, deployment_id)

    agent_decisions = []
    if deployment:
        pipeline_id = deployment.get("pipeline_id")
        if pipeline_id:
            try:
                from boto3.dynamodb.conditions import Key
                result = db.decisions_table.query(
                    KeyConditionExpression=Key("pipeline_id").eq(pipeline_id),
                    Limit=10,
                )
                agent_decisions = _restore_decimals(result.get("Items", []))
            except Exception as e:
                logger.warning(f"Could not load agent decisions: {e}")
                agent_decisions = []

    return {
        "deployment": deployment or {},
        "agent_decisions": agent_decisions,
    }


def _build_prompt(incident: Dict[str, Any], context: Dict[str, Any]) -> str:
    deployment = context.get("deployment", {})
    return SYSTEM_PROMPT_TEMPLATE.format(
        deployment_id=incident.get("deployment_id", "?"),
        severity=incident.get("severity", "?"),
        max_abs_z=incident.get("max_abs_z", "?"),
        triggers_block=_format_triggers(incident.get("anomalous_metrics", [])),
        baseline_block=_format_baseline(incident.get("baseline_snapshot", {})),
        sample_block=_format_sample(incident.get("triggering_sample", {})),
        repo=deployment.get("repo", "?"),
        pr_number=deployment.get("pr_number", "?"),
        head_sha=deployment.get("head_sha", "?"),
        promoted_at=deployment.get("last_updated_at", "?"),
        agent_decisions_block=_format_agent_decisions(context.get("agent_decisions", [])),
    )


def _format_pr_comment(incident: Dict[str, Any], ai_result: Dict[str, Any]) -> str:
    """Build the markdown comment posted to the PR."""
    hints = ai_result.get("investigation_hints", [])
    hints_block = "\n".join(f"- {h}" for h in hints) if hints else "_(none provided)_"

    return f"""## 🚨 Production Incident Detected

**Severity:** {incident.get('severity', '?').upper()}
**Incident ID:** `{incident.get('incident_id', '?')}`
**Max |z-score|:** {incident.get('max_abs_z', '?')}

### Metrics that fired
{incident.get('summary', '_(none)_')}

### 🤖 AI Root Cause Hypothesis
{ai_result.get('root_cause', '_(no hypothesis generated)_')}

**Confidence:** {ai_result.get('confidence', 'unknown').upper()}

### Suggested next step
{ai_result.get('suggested_fix', '_(no fix suggested)_')}

### Investigation hints
{hints_block}

---
*Auto-generated by AgentOps IncidentAgent. This is an AI hypothesis — verify before acting.*
"""


async def _post_to_github(repo: str, pr_number: int, head_sha: str, comment: str) -> bool:
    """Post the AI analysis as a PR comment via the backend webhook."""
    backend_url = os.getenv("BACKEND_URL", "http://backend:4000")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                f"{backend_url}/api/webhooks/post-review",
                json={
                    "repo": repo,
                    "pr_number": pr_number,
                    "comment": comment,
                    "head_sha": head_sha,
                    "decision": "INCIDENT_DETECTED",
                },
            )
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to post incident to GitHub: {e}")
        return False


async def analyze_root_cause(incident: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Main entry point: gather context, call Gemini, save back to incident, post to PR.
    Returns the AI result dict, or None on failure.
    """
    incident_id = incident["incident_id"]
    deployment_id = incident["deployment_id"]

    logger.info(f"[RootCauseAI] Starting analysis for {incident_id}")

    try:
        context = await _gather_context(incident)
        prompt = _build_prompt(incident, context)
        logger.debug(f"[RootCauseAI] Prompt length: {len(prompt)} chars")

        gemini = get_gemini_client()
        ai_result = await gemini.generate_json(
            prompt=prompt,
            use_light_model=False,
            temperature=0.3,
        )

        required_keys = {"root_cause", "suggested_fix", "confidence"}
        missing = required_keys - set(ai_result.keys())
        if missing:
            logger.warning(f"[RootCauseAI] AI response missing keys: {missing}")
            for k in missing:
                ai_result[k] = "(missing from AI response)"
        if "investigation_hints" not in ai_result:
            ai_result["investigation_hints"] = []

        logger.info(
            f"[RootCauseAI] {incident_id} confidence={ai_result['confidence']}: "
            f"{str(ai_result['root_cause'])[:120]}"
        )

        await emit_event(
            Channels.INCIDENTS,
            "incident.root_cause_attached",
            {
                "incident_id": incident_id,
                "deployment_id": deployment_id,
                "ai_confidence": ai_result.get("confidence", "unknown"),
                "root_cause": ai_result.get("root_cause", "")[:300],
                "suggested_fix": ai_result.get("suggested_fix", "")[:200],
            },
            source="RootCauseAI",
        )

        deployment = context.get("deployment", {})
        if deployment.get("repo") and deployment.get("pr_number"):
            comment = _format_pr_comment(incident, ai_result)
            posted = await _post_to_github(
                repo=deployment["repo"],
                pr_number=deployment["pr_number"],
                head_sha=deployment.get("head_sha", ""),
                comment=comment,
            )
            if posted:
                logger.info(f"[RootCauseAI] PR comment posted for {incident_id}")
            else:
                logger.warning(f"[RootCauseAI] PR comment failed for {incident_id}")

        return ai_result

    except Exception as e:
        logger.error(f"[RootCauseAI] Analysis failed for {incident_id}: {e}", exc_info=True)
        return None