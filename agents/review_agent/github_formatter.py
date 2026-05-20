"""
Formats review reports as GitHub Markdown comments.
"""
from typing import Dict, Any, List, Optional


def format_severity_badge(severity: str) -> str:
    """Return a colored badge for a severity level."""
    badges = {
        "critical": "🔴 **CRITICAL**",
        "high": "🟠 **HIGH**",
        "medium": "🟡 **MEDIUM**",
        "low": "🔵 **LOW**",
    }
    return badges.get(severity.lower(), severity.upper())


def format_decision_badge(decision: str) -> str:
    """Return a badge for the review decision."""
    badges = {
        "AUTO_APPROVE": "✅ **AUTO APPROVE**",
        "PASS_WITH_WARNINGS": "✅ **PASS WITH WARNINGS**",
        "REQUEST_CHANGES": "⚠️ **REQUEST CHANGES**",
        "BLOCK": "🚫 **BLOCKED**",
        "REJECT": "❌ **REJECTED**",
    }
    return badges.get(decision, decision)


def format_score_bar(score: int) -> str:
    """Visual progress bar for a score."""
    filled = int(score / 10)
    empty = 10 - filled

    if score >= 85:
        color = "🟢"
    elif score >= 70:
        color = "🟡"
    elif score >= 50:
        color = "🟠"
    else:
        color = "🔴"

    bar = "█" * filled + "░" * empty
    return f"{color} `{bar}` **{score}/100**"


def format_review_comment(report: Dict[str, Any]) -> str:
    """
    Generate a complete GitHub Markdown comment from a review report.
    """
    decision = report["decision"]
    reason = report["reason"]
    scores = report["scores"]
    summary = report["summary"]
    findings = report["findings"]
    duration_ms = report["duration_ms"]

    # Header
    lines = [
        "## 🤖 AgentOps Code Review",
        "",
        f"### {format_decision_badge(decision)}",
        f"*{reason}*",
        "",
        "---",
        "",
        "### 📊 Layer Scores",
        "",
        f"| Layer | Score |",
        f"|-------|-------|",
        f"| **Overall** | {format_score_bar(int(scores['overall']))} |",
        f"| Security | {format_score_bar(scores['security'])} |",
        f"| Code Quality | {format_score_bar(scores['code_quality'])} |",
        f"| Performance | {format_score_bar(scores['performance'])} |",
        f"| Architecture | {format_score_bar(scores['architecture'])} |",
        f"| Test Impact | {format_score_bar(scores['test_impact'])} |",
        f"| Documentation | {format_score_bar(scores['documentation'])} |",
        "",
        "---",
        "",
        f"### 🔍 Findings Summary",
        "",
        f"- 🔴 Critical: **{summary['critical']}**",
        f"- 🟠 High: **{summary['high']}**",
        f"- 🟡 Medium: **{summary['medium']}**",
        f"- 🔵 Low: **{summary['low']}**",
        f"- **Total: {sum(summary.values())}**",
        "",
    ]

    # Detailed findings
    if findings:
        lines.extend([
            "---",
            "",
            "### 📋 Detailed Findings",
            "",
        ])

        # Group findings by severity
        for severity in ["critical", "high", "medium", "low"]:
            severity_findings = [f for f in findings if f["severity"] == severity]
            if not severity_findings:
                continue

            lines.append(f"<details open>")
            lines.append(f"<summary>{format_severity_badge(severity)} ({len(severity_findings)})</summary>")
            lines.append("")

            for f in severity_findings:
                lines.extend(_format_single_finding(f))
                lines.append("")

            lines.append("</details>")
            lines.append("")

    # Footer
    lines.extend([
        "---",
        "",
        f"*🤖 AgentOps reviewed {sum(summary.values())} issue(s) in {duration_ms}ms*",
        f"*Powered by deterministic pattern matching + Google Gemini AI*",
    ])

    return "\n".join(lines)


def format_combined_report(review_report: Dict[str, Any], test_report: Optional[Dict[str, Any]] = None) -> str:
    """
    Combined GitHub comment showing both Review + Test results.
    """
    # Start with the review report
    comment = format_review_comment(review_report)

    if not test_report:
        return comment

    # Append test section
    test_summary = test_report.get("summary", {})
    test_scores = test_report.get("scores", {})
    generated = test_report.get("generated_tests", [])

    lines = [
        "",
        "---",
        "",
        "## 🧪 AgentOps Test Analysis",
        "",
        f"### Decision: **{test_report.get('decision', 'PASS')}**",
        "",
        "### 📊 Test Metrics",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Coverage Score | {format_score_bar(test_scores.get('coverage', 0))} |",
        f"| Source files changed | {test_summary.get('total_source_files', 0)} |",
        f"| Files with existing tests | {test_summary.get('covered_files', 0)} |",
        f"| Files needing tests | {test_summary.get('uncovered_files', 0)} |",
        f"| AI-generated tests | {test_summary.get('tests_generated', 0)} |",
        "",
    ]

    if generated:
        lines.extend([
            "### 🤖 AI-Generated Test Cases",
            "",
            f"<details open>",
            f"<summary>Click to view {len(generated)} suggested tests</summary>",
            "",
        ])

        # Group by target function
        by_function = {}
        for t in generated:
            func = t.get("target_function", "unknown")
            by_function.setdefault(func, []).append(t)

        for func, tests in by_function.items():
            lines.append(f"#### `{func}()`")
            lines.append("")
            for test in tests[:3]:  # Limit to 3 per function to keep comment clean
                lines.extend([
                    f"**{test.get('name', 'Test')}** *({test.get('category', 'happy_path')})*",
                    "",
                    f"> {test.get('description', '')}",
                    "",
                    "```javascript",
                    test.get("code", "").strip(),
                    "```",
                    "",
                ])

        lines.extend(["</details>", ""])

    return comment + "\n".join(lines)

def _format_single_finding(finding: Dict[str, Any]) -> List[str]:
    """Format a single finding as Markdown."""
    method_badge = ""
    if finding.get("detection_method") == "regex":
        method_badge = " *(detected by regex)*"
    elif finding.get("detection_method") == "ai":
        method_badge = " *(detected by AI)*"

    lines = [
        f"**`{finding['file']}:{finding['line']}`** — {finding['title']}{method_badge}",
        "",
        f"> {finding['description']}",
        "",
    ]

    # Code snippet
    if finding.get("code_snippet"):
        snippet = finding["code_snippet"].strip()
        # Detect language from extension
        ext = finding['file'].split('.')[-1] if '.' in finding['file'] else ''
        lang_map = {
            'js': 'javascript', 'jsx': 'jsx', 'ts': 'typescript', 'tsx': 'tsx',
            'py': 'python', 'java': 'java', 'go': 'go', 'rb': 'ruby'
        }
        lang = lang_map.get(ext, '')

        lines.extend([
            f"```{lang}",
            snippet,
            "```",
            "",
        ])

    # Suggested fix
    if finding.get("suggested_fix"):
        lines.extend([
            f"**💡 Suggested fix:** {finding['suggested_fix']}",
        ])

    return lines