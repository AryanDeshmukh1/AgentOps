"""
ReviewAgent — Orchestrates the 6-layer code review.
"""
import time
from dataclasses import asdict
from typing import List, Dict, Any

from review_agent.pattern_scanner import scan_patch, Finding, Severity
from review_agent.ai_analyzer import run_ai_analysis
from shared.logger import get_logger

logger = get_logger(__name__)


WEIGHTS = {
    "security":      0.30,
    "code_quality":  0.20,
    "performance":   0.15,
    "architecture":  0.15,
    "test_impact":   0.10,
    "documentation": 0.10,
}


def calculate_security_score(findings: List[Finding]) -> int:
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
    total = sum(
        layer_scores.get(layer, 80) * weight
        for layer, weight in WEIGHTS.items()
    )
    return round(max(0, min(100, total)), 1)


def determine_decision(overall_score: float, has_critical: bool) -> tuple[str, str]:
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
    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        summary[f.severity.value] += 1
    return summary


def deduplicate_findings(findings: List[Finding]) -> List[Finding]:
    """
    Merge duplicate findings using fuzzy title matching.
    Same file + same line + similar title = duplicate.
    Regex findings preferred over AI findings.
    """
    # First pass: group by (file, line)
    grouped = {}
    for finding in findings:
        key = (finding.file, finding.line)
        grouped.setdefault(key, []).append(finding)

    deduplicated = []
    for (file, line), group in grouped.items():
        if len(group) == 1:
            deduplicated.append(group[0])
            continue

        # Group by category to find true duplicates
        by_category = {}
        for f in group:
            by_category.setdefault(f.category, []).append(f)

        for category, items in by_category.items():
            if len(items) == 1:
                deduplicated.append(items[0])
            else:
                # Multiple findings for same file+line+category — keep regex if any, else first
                regex_findings = [i for i in items if i.detection_method == "regex"]
                if regex_findings:
                    deduplicated.append(regex_findings[0])
                else:
                    deduplicated.append(items[0])

    return deduplicated


def _is_code_file(filename: str) -> bool:
    code_extensions = (
        ".js", ".jsx", ".ts", ".tsx", ".mjs",
        ".py", ".java", ".go", ".rb", ".php",
        ".c", ".cpp", ".h", ".hpp", ".cs",
        ".rs", ".swift", ".kt", ".scala",
    )
    return filename.endswith(code_extensions)


async def run_review(pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
    pipeline_id = pipeline_data["pipeline_id"]
    files = pipeline_data["files"]

    logger.info(f"[{pipeline_id}] ReviewAgent starting on {len(files)} file(s)")
    start_time = time.time()

    all_regex_findings: List[Finding] = []
    all_ai_findings: List[Finding] = []

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
            continue
        if not patch:
            continue

        regex_findings = scan_patch(filename, patch)
        logger.info(f"[{pipeline_id}] Layer 1 ({filename}): {len(regex_findings)} findings")
        all_regex_findings.extend(regex_findings)

        ai_result = await run_ai_analysis(filename, patch, pipeline_id)
        ai_findings = ai_result["findings"]
        ai_scores = ai_result["scores"]

        logger.info(f"[{pipeline_id}] Layers 2-6 ({filename}): {len(ai_findings)} findings")
        all_ai_findings.extend(ai_findings)

        for layer, score in ai_scores.items():
            if layer in layer_scores_per_file:
                layer_scores_per_file[layer].append(score)

    combined = all_regex_findings + all_ai_findings
    all_findings = deduplicate_findings(combined)
    logger.info(f"[{pipeline_id}] Deduplicated {len(combined)} -> {len(all_findings)} findings")

    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
    }
    all_findings.sort(key=lambda f: severity_order[f.severity])

    security_score = calculate_security_score(all_regex_findings)
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
        "scores": {**all_layer_scores, "overall": overall_score},
        "decision": decision,
        "reason": reason,
        "findings": [asdict(f) for f in all_findings],
    }

    logger.info(
        f"[{pipeline_id}] ReviewAgent complete in {duration_ms}ms - "
        f"overall={overall_score}, decision={decision}, findings={len(all_findings)}"
    )

    return report
