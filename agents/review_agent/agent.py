"""
ReviewAgent — Orchestrates the 6-layer code review.
- Layer 1: Regex-based pattern scanner (security)
- Layers 2-6: AI-powered analysis (Gemini)
"""
import time
from dataclasses import asdict
from typing import List, Dict, Any

from review_agent.pattern_scanner import scan_patch, Finding, Severity
from review_agent.ai_analyzer import run_ai_analysis
from shared.logger import get_logger

logger = get_logger(__name__)


# Layer weights for overall score
WEIGHTS = {
    "security":      0.30,
    "code_quality":  0.20,
    "performance":   0.15,
    "architecture":  0.15,
    "test_impact":   0.10,
    "documentation": 0.10,
}


def calculate_security_score(findings: List[Finding]) -> int:
    """Layer 1 score based on regex findings."""
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


def calculate_overall_score(layer_scores: Dict[str, int]) -> float:
    """Weighted overall score across all 6 layers."""
    total = sum(
        layer_scores.get(layer, 80) * weight
        for layer, weight in WEIGHTS.items()
    )
    return round(max(0, min(100, total)), 1)


def determine_decision(overall_score: float, has_critical: bool) -> tuple[str, str]:
    """Decision logic based on overall score and critical findings."""
    if has_critical:
        return "BLOCK", "Critical security finding(s) detected"
    elif overall_score >= 85:
        return "AUTO_APPROVE", "High confidence, low risk"
    elif overall_score >= 70:
        return "PASS_WITH_WARNINGS", "Acceptable but has areas for improvement"
    elif overall_score >= 50:
        return "REQUEST_CHANGES", "Multiple issues need attention"
    else:
        return "REJECT", "Significant issues require rework"


def summarize_findings(findings: List[Finding]) -> Dict[str, int]:
    """Count findings by severity."""
    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        summary[f.severity.value] += 1
    return summary


def deduplicate_findings(findings: List[Finding]) -> List[Finding]:
    """
    Merge duplicate findings that detect the same issue.
    Two findings are duplicates if they have the same file, same line,
    and similar category (security duplicates from both regex and AI).
    """
    seen = {}  # key: (file, line, normalized_title) -> Finding
    deduplicated = []

    for finding in findings:
        # Create a fuzzy match key
        # Normalize titles like "Hardcoded API key" and "Hardcoded API Key"
        normalized_title = finding.title.lower().strip()

        # Take first 3 words of normalized title for grouping
        title_key = " ".join(normalized_title.split()[:3])
        key = (finding.file, finding.line, title_key)

        if key not in seen:
            seen[key] = finding
            deduplicated.append(finding)
        else:
            # Prefer regex detection over AI (regex is deterministic)
            # If existing is AI and new is regex, replace
            existing = seen[key]
            if existing.detection_method == "ai" and finding.detection_method == "regex":
                # Replace AI version with regex version
                deduplicated.remove(existing)
                deduplicated.append(finding)
                seen[key] = finding

    return deduplicated


async def run_review(pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the complete 6-layer code review.
    """
    pipeline_id = pipeline_data["pipeline_id"]
    files = pipeline_data["files"]

    logger.info(f"[{pipeline_id}] ReviewAgent starting on {len(files)} file(s)")
    start_time = time.time()

    all_regex_findings: List[Finding] = []
    all_ai_findings: List[Finding] = []

    # Layer scores aggregated across all files (average per layer)
    layer_scores_per_file: Dict[str, List[int]] = {
        "code_quality": [],
        "performance": [],
        "architecture": [],
        "test_impact": [],
        "documentation": [],
    }

    for file_data in files:
        filename = file_data["filename"]
        patch = file_data.get("patch", "")

        if not _is_code_file(filename):
            logger.debug(f"[{pipeline_id}] Skipping non-code file: {filename}")
            continue

        if not patch:
            logger.debug(f"[{pipeline_id}] No patch for {filename}")
            continue

        # Layer 1: Regex scan
        regex_findings = scan_patch(filename, patch)
        logger.info(f"[{pipeline_id}] Layer 1 ({filename}): {len(regex_findings)} findings")
        all_regex_findings.extend(regex_findings)

        # Layers 2-6: AI analysis
        ai_result = await run_ai_analysis(filename, patch, pipeline_id)
        ai_findings = ai_result["findings"]
        ai_scores = ai_result["scores"]

        logger.info(f"[{pipeline_id}] Layers 2-6 ({filename}): {len(ai_findings)} findings")
        all_ai_findings.extend(ai_findings)

        for layer, score in ai_scores.items():
            if layer in layer_scores_per_file:
                layer_scores_per_file[layer].append(score)

    # Combine all findings
    all_findings = all_regex_findings + all_ai_findings

    # Sort by severity
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
    }
    all_findings.sort(key=lambda f: severity_order[f.severity])

    # Calculate scores
    security_score = calculate_security_score(all_regex_findings)

    # Average AI scores across files (default to 90 if no AI ran)
    avg_ai_scores = {
        layer: int(sum(scores) / len(scores)) if scores else 90
        for layer, scores in layer_scores_per_file.items()
    }

    all_layer_scores = {
        "security": security_score,
        **avg_ai_scores,
    }

    overall_score = calculate_overall_score(all_layer_scores)
    summary = summarize_findings(all_findings)
    has_critical = summary["critical"] > 0
    decision, reason = determine_decision(overall_score, has_critical)

    duration_ms = int((time.time() - start_time) * 1000)

    report = {
        "pipeline_id": pipeline_id,
        "agent": "ReviewAgent",
        "duration_ms": duration_ms,
        "summary": summary,
        "scores": {
            **all_layer_scores,
            "overall": overall_score,
        },
        "decision": decision,
        "reason": reason,
        "findings": [asdict(f) for f in all_findings],
    }

    logger.info(
        f"[{pipeline_id}] ReviewAgent complete in {duration_ms}ms — "
        f"overall={overall_score}, decision={decision}, findings={len(all_findings)}"
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