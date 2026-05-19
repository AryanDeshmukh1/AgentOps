"""
Layers 2-6: AI-powered analysis using Gemini.
"""
import re
from typing import List, Dict, Any

from review_agent.pattern_scanner import Finding, Severity
from shared.gemini_client import get_gemini_client
from shared.logger import get_logger

logger = get_logger(__name__)


AI_REVIEW_PROMPT = """You are a senior code reviewer analyzing a pull request diff.
Be CRITICAL but ACCURATE. Only report REAL issues, not theoretical ones.

IMPORTANT RULES:
1. Do NOT report security issues (hardcoded secrets, SQL injection, eval, etc.) — those are handled separately by a regex scanner.
2. Focus on CODE QUALITY, PERFORMANCE, ARCHITECTURE, TEST IMPACT, and DOCUMENTATION only.
3. If something is acceptable code (just because it's intentionally bad for testing), still flag it.
4. Avoid duplicates: report each issue ONCE even if it appears multiple times.
5. Be specific: cite exact line numbers and quote the problematic code.

WHAT TO ANALYZE (NOT security — that's handled elsewhere):

CODE QUALITY (most important):
- Functions over 30 lines (suggest breaking them up)
- Deep nesting (more than 3 levels of if/else/loops)
- Poor variable names (single chars like x, y; generic like data, temp, result)
- Magic numbers without named constants
- Missing error handling (no try/catch, swallowed errors)
- Functions doing multiple things (single responsibility violation)
- Commented-out code left in the diff

PERFORMANCE:
- N+1 queries (DB calls inside loops)
- Missing pagination on list operations
- Synchronous I/O blocking async code
- Memory leaks (listeners/intervals not cleaned up)
- Expensive operations without caching

ARCHITECTURE:
- Business logic in route handlers (should be in service layer)
- REST violations (wrong HTTP verbs, inconsistent URLs)
- Wrong HTTP status codes (200 for errors)
- Hardcoded URLs, ports, environment-specific values

TEST IMPACT:
- New functions or routes without tests
- Modified signatures that would break existing tests
- Tests removed or commented out

DOCUMENTATION:
- Missing JSDoc on exported/public functions
- TODO/FIXME/HACK markers in production code
- Complex logic without explanatory comments

CODE TO REVIEW:
{code_to_review}

FILE: {filename}

Return ONLY a JSON object (no markdown fences, no preamble):
{{
  "findings": [
    {{
      "severity": "high|medium|low",
      "category": "code_quality|performance|architecture|test_impact|documentation",
      "title": "Short specific title (5-10 words)",
      "line": <line_number>,
      "code_snippet": "exact problematic code from that line",
      "description": "What's wrong and why it matters (1-2 sentences)",
      "suggested_fix": "Concrete how-to-fix (1 sentence)"
    }}
  ],
  "scores": {{
    "code_quality": <0-100>,
    "performance": <0-100>,
    "architecture": <0-100>,
    "test_impact": <0-100>,
    "documentation": <0-100>
  }}
}}

Scoring guide:
- 90-100: Excellent, no issues
- 70-89: Good, 1-2 minor issues
- 50-69: Acceptable, multiple issues to address
- 0-49: Poor, significant problems

Severity guide:
- high: Will cause bugs or major maintenance issues
- medium: Should be fixed soon, technical debt accumulating
- low: Style/preference, nice to fix
"""


def _extract_added_lines(patch: str) -> str:
    """Extract added lines from a git patch with file line numbers."""
    lines = []
    file_line = 0
    in_hunk = False

    for line in patch.split("\n"):
        if line.startswith("@@"):
            match = re.search(r'\+(\d+)', line)
            if match:
                file_line = int(match.group(1)) - 1
                in_hunk = True
            continue

        if line.startswith("---") or line.startswith("+++"):
            continue

        if not in_hunk and (line.startswith("+") or line.startswith(" ")):
            in_hunk = True
            file_line = 0

        if line.startswith("+"):
            file_line += 1
            content = line[1:]
            lines.append(f"{file_line}: {content}")
        elif line.startswith(" "):
            file_line += 1

    return "\n".join(lines)


async def run_ai_analysis(filename: str, patch: str, pipeline_id: str) -> Dict[str, Any]:
    """Run AI-powered analysis on the patch for layers 2-6."""
    code_with_lines = _extract_added_lines(patch)

    if not code_with_lines.strip():
        logger.info(f"[{pipeline_id}] No added lines in {filename}, skipping AI")
        return {
            "findings": [],
            "scores": {
                "code_quality": 100,
                "performance": 100,
                "architecture": 100,
                "test_impact": 100,
                "documentation": 100,
            },
        }

    prompt = AI_REVIEW_PROMPT.format(
        code_to_review=code_with_lines,
        filename=filename,
    )

    logger.info(f"[{pipeline_id}] Calling Gemini for {filename} ({len(code_with_lines)} chars)")

    try:
        client = get_gemini_client()
        response = await client.generate_json(prompt, temperature=0.2)

        findings_raw = response.get("findings", [])
        scores = response.get("scores", {})

        findings: List[Finding] = []
        for f in findings_raw:
            severity_str = f.get("severity", "low").lower()
            try:
                severity = Severity(severity_str)
            except ValueError:
                severity = Severity.LOW

            findings.append(Finding(
                severity=severity,
                category=f.get("category", "unknown"),
                title=f.get("title", "Issue"),
                file=filename,
                line=int(f.get("line", 0)),
                code_snippet=str(f.get("code_snippet", ""))[:200],
                description=f.get("description", ""),
                suggested_fix=f.get("suggested_fix", ""),
                detection_method="ai",
            ))

        logger.info(
            f"[{pipeline_id}] Gemini analysis complete for {filename}: "
            f"{len(findings)} findings, scores={scores}"
        )

        return {
            "findings": findings,
            "scores": {
                "code_quality": int(scores.get("code_quality", 80)),
                "performance": int(scores.get("performance", 80)),
                "architecture": int(scores.get("architecture", 80)),
                "test_impact": int(scores.get("test_impact", 80)),
                "documentation": int(scores.get("documentation", 80)),
            },
        }

    except Exception as e:
        logger.error(f"[{pipeline_id}] AI analysis failed for {filename}: {e}", exc_info=True)
        return {
            "findings": [],
            "scores": {
                "code_quality": 80,
                "performance": 80,
                "architecture": 80,
                "test_impact": 80,
                "documentation": 80,
            },
            "error": str(e),
        }
