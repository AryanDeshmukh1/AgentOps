"""
ReviewAgent — Orchestrates the 6-layer code review.
Currently implements Layer 1 (regex pattern scanning).
Layers 2-6 will be added in subsequent days.
"""
import time
from dataclasses import asdict
from typing import List, Dict, Any

from review_agent.pattern_scanner import scan_patch, Finding, Severity
from shared.logger import get_logger

logger = get_logger(__name__)


def calculate_layer_1_score(findings: List[Finding]) -> int:
    """
    Calculate security score (0-100) based on findings.
    Each finding deducts points based on severity.
    """
    score = 100
    for f in findings:
        if f.severity == Severity.CRITICAL:
            score -= 25
        elif f.severity == Severity.HIGH:
            score -= 10
        elif f.severity == Severity.MEDIUM:
            score -= 5
        elif f.severity == Severity.LOW:
            score -= 2
    return max(0, score)


def summarize_findings(findings: List[Finding]) -> Dict[str, int]:
    """Count findings by severity."""
    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        summary[f.severity.value] += 1
    return summary


async def run_review(pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run a code review on the given pipeline data.

    Args:
        pipeline_data: Dict with pipeline_id, repo, pr_number, files, etc.

    Returns:
        Review report dict with findings, scores, and decision.
    """
    pipeline_id = pipeline_data["pipeline_id"]
    files = pipeline_data["files"]

    logger.info(f"[{pipeline_id}] ReviewAgent starting analysis on {len(files)} file(s)")
    start_time = time.time()

    # Run Layer 1: Pattern scanner on all changed files
    all_findings: List[Finding] = []
    for file_data in files:
        filename = file_data["filename"]
        patch = file_data.get("patch", "")

       

        # Skip non-code files
        if not _is_code_file(filename):
            logger.debug(f"[{pipeline_id}] Skipping non-code file: {filename}")
            continue

        if not patch:
            logger.debug(f"[{pipeline_id}] No patch content for {filename}, skipping")
            continue

        file_findings = scan_patch(filename, patch)
        logger.info(f"[{pipeline_id}] Scanned {filename}: found {len(file_findings)} issues")
        if file_findings: 
            all_findings.extend(file_findings)

    # Sort by severity (critical first)
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
    }
    all_findings.sort(key=lambda f: severity_order[f.severity])

    # Calculate scores
    layer_1_score = calculate_layer_1_score(all_findings)
    summary = summarize_findings(all_findings)

    # Decision logic for Layer 1 only (full 6-layer scoring comes later)
    has_critical = summary["critical"] > 0
    if has_critical:
        decision = "BLOCK"
        reason = f"{summary['critical']} critical security finding(s) detected"
    elif layer_1_score >= 85:
        decision = "PASS"
        reason = "No significant security issues"
    elif layer_1_score >= 70:
        decision = "PASS_WITH_WARNINGS"
        reason = "Minor issues found but acceptable"
    else:
        decision = "REQUEST_CHANGES"
        reason = "Multiple security issues need attention"

    duration_ms = int((time.time() - start_time) * 1000)

    report = {
        "pipeline_id": pipeline_id,
        "agent": "ReviewAgent",
        "layer": 1,
        "duration_ms": duration_ms,
        "summary": summary,
        "scores": {
            "security": layer_1_score,
        },
        "decision": decision,
        "reason": reason,
        "findings": [asdict(f) for f in all_findings],
    }

    logger.info(
        f"[{pipeline_id}] ReviewAgent Layer 1 complete in {duration_ms}ms — "
        f"score={layer_1_score}, decision={decision}, findings={len(all_findings)}"
    )

    return report


def _is_code_file(filename: str) -> bool:
    """Check if a file should be analyzed."""
    code_extensions = (
        ".js", ".jsx", ".ts", ".tsx", ".mjs",
        ".py", ".java", ".go", ".rb", ".php",
        ".c", ".cpp", ".h", ".hpp", ".cs",
        ".rs", ".swift", ".kt", ".scala",
    )
    return filename.endswith(code_extensions)