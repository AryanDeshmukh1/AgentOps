"""
AnomalyDetector — compares a new sample to a baseline using Z-scores.

For each metric, computes z = (current - mean) / stddev.
Fires an anomaly if |z| exceeds the per-metric threshold AND direction matches.

Direction config — what counts as "bad" for each metric:
  - error_rate_pct:    "up"   (spikes are bad; drops are fine)
  - latency_p95_ms:    "up"   (slow is bad; fast is fine)
  - request_volume_rpm: "down" (traffic loss is concerning; spikes usually fine)
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from shared.logger import get_logger

logger = get_logger(__name__)


# Per-metric configuration: threshold (z-score) and direction of concern
METRIC_CONFIG = {
    "error_rate_pct": {"threshold": 3.0, "direction": "up"},
    "latency_p95_ms": {"threshold": 3.0, "direction": "up"},
    "request_volume_rpm": {"threshold": 3.0, "direction": "down"},
}


def _severity_for_z(abs_z: float) -> str:
    """Map Z-score magnitude to severity label."""
    if abs_z >= 6.0:
        return "critical"
    if abs_z >= 4.0:
        return "high"
    return "warning"


def _is_anomalous(z: float, direction: str, threshold: float) -> bool:
    """Whether this Z-score, in this direction, crosses the threshold."""
    if direction == "up":
        return z > threshold
    if direction == "down":
        return z < -threshold
    return abs(z) > threshold  # "both" — for future use


@dataclass
class MetricAnomaly:
    """One metric's anomaly detection result."""
    name: str
    current_value: float
    baseline_mean: float
    baseline_stddev: float
    z_score: float
    threshold: float
    direction: str
    is_anomalous: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "current_value": self.current_value,
            "baseline_mean": self.baseline_mean,
            "baseline_stddev": self.baseline_stddev,
            "z_score": round(self.z_score, 3),
            "threshold": self.threshold,
            "direction": self.direction,
            "is_anomalous": self.is_anomalous,
        }


def detect_anomalies(
    current_sample: Dict[str, Any],
    baseline: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run anomaly detection on one sample against a baseline.

    Returns: {
        "any_anomaly": bool,
        "severity": str | None,
        "anomalous_metrics": [MetricAnomaly dicts where is_anomalous=True],
        "all_metrics": [all MetricAnomaly dicts, for forensics],
        "max_abs_z": float,
    }
    """
    anomalies: List[MetricAnomaly] = []
    max_abs_z = 0.0
    baseline_metrics = baseline.get("metrics", {})

    for metric_name, cfg in METRIC_CONFIG.items():
        if metric_name not in current_sample:
            continue
        if metric_name not in baseline_metrics:
            continue

        current_val = float(current_sample[metric_name])
        mean = float(baseline_metrics[metric_name]["mean"])
        stddev = float(baseline_metrics[metric_name]["stddev"])

        # Skip metrics with near-zero stddev (no variance = no signal)
        if stddev < 0.001:
            continue

        z = (current_val - mean) / stddev
        flagged = _is_anomalous(z, cfg["direction"], cfg["threshold"])

        anomaly = MetricAnomaly(
            name=metric_name,
            current_value=current_val,
            baseline_mean=mean,
            baseline_stddev=stddev,
            z_score=z,
            threshold=cfg["threshold"],
            direction=cfg["direction"],
            is_anomalous=flagged,
        )
        anomalies.append(anomaly)

        if abs(z) > max_abs_z:
            max_abs_z = abs(z)

    flagged_anomalies = [a for a in anomalies if a.is_anomalous]
    any_anomaly = len(flagged_anomalies) > 0
    severity = _severity_for_z(max_abs_z) if any_anomaly else None

    return {
        "any_anomaly": any_anomaly,
        "severity": severity,
        "max_abs_z": round(max_abs_z, 3),
        "anomalous_metrics": [a.to_dict() for a in flagged_anomalies],
        "all_metrics": [a.to_dict() for a in anomalies],
    }