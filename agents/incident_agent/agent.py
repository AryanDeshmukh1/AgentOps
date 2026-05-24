"""
IncidentAgent — the third sibling to ReviewAgent and DeployAgent.

For each new metric sample on a promoted deployment, this agent:
  1. Loads the rolling baseline
  2. Runs anomaly detection (Z-score)
  3. If anomalous AND no open incident exists for this deployment, fires one
  4. Cooldown: suppresses duplicate incidents for INCIDENT_COOLDOWN_MINUTES

Day 19 will add: AI-driven root cause analysis on each fired incident.
"""
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from incident_agent.anomaly_detector import detect_anomalies
from incident_agent.baseline import compute_baseline, has_usable_baseline
from shared.dynamodb_service import get_dynamodb_service
from shared.logger import get_logger

logger = get_logger(__name__)


INCIDENT_COOLDOWN_MINUTES = int(os.getenv("INCIDENT_COOLDOWN_MINUTES", "5"))


def _build_incident_id(deployment_id: str) -> str:
    return f"incident_{deployment_id}_{int(time.time())}"


async def _has_recent_open_incident(db, deployment_id: str) -> bool:
    """Cooldown: any open incident in the last INCIDENT_COOLDOWN_MINUTES?"""
    incidents = await db.list_recent_incidents(deployment_id, limit=5)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=INCIDENT_COOLDOWN_MINUTES)
    for inc in incidents:
        if inc.get("status") != "open":
            continue
        created_at = inc.get("created_at")
        if not created_at:
            continue
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if created > cutoff:
                return True
        except (ValueError, TypeError):
            continue
    return False


async def evaluate_sample(deployment_id: str, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Entry point: called by metric_worker after each new sample.

    Returns the incident record if one was created, else None.
    """
    db = get_dynamodb_service()

    # 1. Need a baseline to compare against
    baseline = await compute_baseline(deployment_id, window_samples=20)
    if not has_usable_baseline(baseline):
        return None

    # 2. Run detection
    detection = detect_anomalies(sample, baseline)
    if not detection["any_anomaly"]:
        return None

    # 3. Cooldown gate
    if await _has_recent_open_incident(db, deployment_id):
        logger.info(
            f"[IncidentAgent] Suppressed (cooldown active): {deployment_id} "
            f"max_z={detection['max_abs_z']}"
        )
        return None

    # 4. Fire incident
    incident_id = _build_incident_id(deployment_id)
    now = datetime.now(timezone.utc).isoformat()

    # Build a concise summary line (used by Day 19 for the root-cause prompt)
    triggers = ", ".join(
        f"{m['name']}={m['current_value']} (z={m['z_score']:+.1f})"
        for m in detection["anomalous_metrics"]
    )

    incident = {
        "deployment_id": deployment_id,
        "incident_id": incident_id,
        "created_at": now,
        "status": "open",
        "severity": detection["severity"],
        "max_abs_z": detection["max_abs_z"],
        "summary": triggers,
        "triggering_sample": sample,
        "baseline_snapshot": baseline,
        "anomalous_metrics": detection["anomalous_metrics"],
        "all_metrics": detection["all_metrics"],
        "root_cause": None,           # Day 19 fills this
        "suggested_fix": None,        # Day 19 fills this
        "acknowledged_by": None,
        "acknowledged_at": None,
        "resolved_by": None,
        "resolved_at": None,
    }

    ok = await db.save_incident(incident)
    if not ok:
        return None

    logger.warning(
        f"[IncidentAgent] INCIDENT FIRED — {incident_id} "
        f"severity={detection['severity']} {triggers}"
    )
    return incident