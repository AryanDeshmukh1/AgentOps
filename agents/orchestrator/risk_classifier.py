"""
Risk classification for PRs.
"""
from typing import List, Dict, Any
from enum import Enum


class RiskLevel(str, Enum):
    AUTO = "auto"
    SOFT = "soft"
    HARD = "hard"


CRITICAL_PATH_PATTERNS = [
    "auth", "security", "permission", "iam", "rbac",
    "payment", "billing", "checkout", "stripe",
    "crypto", "encrypt", "secret",
    "migration", "schema",
    ".github/workflows", "docker", "kubernetes",
    "production", "prod-config",
]


def classify_risk(review_report=None, test_report=None, files=None):
    files = files or []
    critical_files = []

    for file in files:
        filename = file.get("filename", "").lower()
        for pattern in CRITICAL_PATH_PATTERNS:
            if pattern in filename:
                critical_files.append(file.get("filename"))
                break

    decision = review_report.get("decision", "PASS") if review_report else "PASS"
    overall_score = review_report.get("scores", {}).get("overall", 100) if review_report else 100
    critical_findings = review_report.get("summary", {}).get("critical", 0) if review_report else 0
    coverage = test_report.get("scores", {}).get("coverage", 100) if test_report else 100

    if decision == "BLOCK" or critical_findings > 0:
        return {
            "risk_level": RiskLevel.HARD.value,
            "reason": "Critical security issues detected",
            "requires_approval": True,
            "critical_files": critical_files,
        }

    if critical_files:
        return {
            "risk_level": RiskLevel.HARD.value,
            "reason": f"Changes touch critical paths: {', '.join(critical_files[:3])}",
            "requires_approval": True,
            "critical_files": critical_files,
        }

    if decision == "REQUEST_CHANGES" or overall_score < 70 or coverage < 50:
        return {
            "risk_level": RiskLevel.SOFT.value,
            "reason": "Quality concerns - optional approval recommended",
            "requires_approval": True,
            "critical_files": critical_files,
        }

    if decision == "AUTO_APPROVE" and overall_score >= 85:
        return {
            "risk_level": RiskLevel.AUTO.value,
            "reason": "High-quality PR - auto-approved",
            "requires_approval": False,
            "critical_files": [],
        }

    return {
        "risk_level": RiskLevel.SOFT.value,
        "reason": "Standard PR - optional approval",
        "requires_approval": True,
        "critical_files": critical_files,
    }
