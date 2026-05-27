"""
MetricCollector — samples deployment metrics and persists them.

For Day 17: generates synthetic but realistic metrics (Gaussian noise around
healthy baselines, with occasional jitter). On Day 33, swap the sampler for
real CloudWatch / Prometheus calls — same interface.
"""
import random
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from shared.dynamodb_service import get_dynamodb_service
from shared.logger import get_logger

logger = get_logger(__name__)


# Healthy baseline ranges for synthetic generation.
# Tweak these if you want to simulate different production profiles.
HEALTHY_BASELINES = {
    "error_rate_pct": {"mean": 0.5, "stddev": 0.3, "floor": 0.0},
    "latency_p95_ms": {"mean": 120.0, "stddev": 25.0, "floor": 30.0},
    "request_volume_rpm": {"mean": 2500.0, "stddev": 400.0, "floor": 50.0},
}

# When this is True, the next sample is forced to be a clear anomaly.
# Used by tests/demos to trigger Day 18's detector deterministically.
INJECT_ANOMALY_NEXT = {"enabled": False, "spike_factor": 12.0}


def _sample_metric(name: str, anomaly: bool = False) -> float:
    """Sample one metric value. Optionally force an anomaly spike."""
    cfg = HEALTHY_BASELINES[name]
    value = random.gauss(cfg["mean"], cfg["stddev"])
    value = max(cfg["floor"], value)
    if anomaly:
        value = cfg["mean"] + cfg["stddev"] * INJECT_ANOMALY_NEXT["spike_factor"]
    return round(value, 3)


def generate_synthetic_sample(deployment_id: str) -> Dict[str, Any]:
    """Generate one metric sample for a deployment."""
    anomaly = INJECT_ANOMALY_NEXT["enabled"]
    if anomaly:
        INJECT_ANOMALY_NEXT["enabled"] = False  # one-shot
        logger.warning(f"[MetricCollector] Anomaly injected for {deployment_id}")

    now = datetime.now(timezone.utc)
    ttl_epoch = int((now + timedelta(hours=24)).timestamp())

    return {
        "deployment_id": deployment_id,
        "metric_timestamp": now.isoformat(),
        "error_rate_pct": _sample_metric("error_rate_pct", anomaly),
        "latency_p95_ms": _sample_metric("latency_p95_ms", anomaly),
        "request_volume_rpm": _sample_metric("request_volume_rpm", anomaly=False),
        "source": "synthetic",
        "ttl": ttl_epoch,
        "anomaly_injected": anomaly,
    }


async def collect_one_sample(deployment_id: str) -> Optional[Dict[str, Any]]:
    """Generate and persist one metric sample for a deployment."""
    sample = generate_synthetic_sample(deployment_id)
    db = get_dynamodb_service()
    ok = await db.save_metric_sample(sample)
    if not ok:
        return None
    logger.info(
        f"[MetricCollector] {deployment_id}: "
        f"err={sample['error_rate_pct']}%, "
        f"p95={sample['latency_p95_ms']}ms, "
        f"rpm={sample['request_volume_rpm']}"
    )
    return sample