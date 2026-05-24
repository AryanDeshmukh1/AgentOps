"""
BaselineCalculator — computes rolling mean and stddev for each metric stream.

Day 18's anomaly detector will compare new samples against these baselines
using Z-scores: z = (current - mean) / stddev.
"""
import statistics
from typing import Dict, Any, List, Optional

from shared.dynamodb_service import get_dynamodb_service
from shared.logger import get_logger

logger = get_logger(__name__)


METRIC_FIELDS = ["error_rate_pct", "latency_p95_ms", "request_volume_rpm"]

# Minimum samples required before a baseline is considered usable.
# Below this, anomaly detection skips (avoid noisy false positives).
MIN_SAMPLES_FOR_BASELINE = 10


async def compute_baseline(
    deployment_id: str,
    window_samples: int = 20,
) -> Optional[Dict[str, Any]]:
    """
    Compute mean + stddev for each metric over the last `window_samples`.

    Returns None if not enough samples yet (deployment too fresh).
    """
    db = get_dynamodb_service()
    samples = await db.list_recent_metrics(deployment_id, limit=window_samples)

    if len(samples) < MIN_SAMPLES_FOR_BASELINE:
        logger.info(
            f"[Baseline] {deployment_id}: insufficient samples "
            f"({len(samples)}/{MIN_SAMPLES_FOR_BASELINE} required)"
        )
        return None

    baseline = {
        "deployment_id": deployment_id,
        "sample_count": len(samples),
        "metrics": {},
    }

    for field in METRIC_FIELDS:
        values = [float(s[field]) for s in samples if field in s]
        if len(values) < 2:
            continue
        mean = statistics.mean(values)
        stddev = statistics.stdev(values) if len(values) > 1 else 0.0
        baseline["metrics"][field] = {
            "mean": round(mean, 3),
            "stddev": round(stddev, 3),
            "min": round(min(values), 3),
            "max": round(max(values), 3),
            "n": len(values),
        }

    return baseline


def has_usable_baseline(baseline: Optional[Dict[str, Any]]) -> bool:
    """Whether the baseline has enough data for anomaly detection."""
    if not baseline:
        return False
    return baseline.get("sample_count", 0) >= MIN_SAMPLES_FOR_BASELINE