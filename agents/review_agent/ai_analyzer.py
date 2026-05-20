"""
Layers 2-6: AI-powered analysis using Gemini.
Now sends full file context alongside the diff for better understanding.
"""
import re
from typing import List, Dict, Any

from review_agent.pattern_scanner import Finding, Severity
from shared.gemini_client import get_gemini_client
from shared.logger import get_logger

logger = get_logger(__name__)


AI_REVIEW_PROMPT = """You are a senior code reviewer analyzing a pull request diff.
Be CRITICAL but ACCURATE. Only report REAL issues.

IMPORTANT RULES:
1. DO NOT report security issues (hardcoded secrets, SQL injection, eval, etc.) - those are handled separately by a regex scanner.
2. Focus on CODE QUALITY, PERFORMANCE, ARCHITECTURE, TEST IMPACT, and DOCUMENTATION only.
3. Avoid duplicates: report each unique issue ONCE.
4. Be specific: cite exact line numbers and quote the problematic code.
5. For each finding, also rate your CONFIDENCE (high/medium/low) in whether it's actually an issue.

WHAT TO ANALYZE:

CODE QUALITY:
- Functions over 30 lines
- Deep nesting (more than 3 levels)
- Poor variable names (single chars; generic like data, temp, result)
- Magic numbers without named constants
- Missing error handling (no try/catch, swallowed errors)
- Functions doing multiple things
- Commented-out code

PERFORMANCE:
- N+1 queries (DB calls inside loops)
- Missing pagination
- Synchronous I/O blocking async code
- Memory leaks

ARCHITECTURE:
- Business logic in route handlers
- REST violations (wrong HTTP verbs)
- Wrong HTTP status codes
- Hardcoded URLs, ports, environment-specific values

TEST IMPACT:
- New functions without tests (high priority for critical paths)
- Modified signatures that would break existing tests

DOCUMENTATION:
- Missing JSDoc/docstrings on exported functions
- TODO/FIXME/HACK markers
- Complex logic without explanatory comments

FILE CONTEXT (for understanding only):
{file_context}

CHANGES TO REVIEW (with line numbers):
{code_to_review}

FILE: {filename}

Return ONLY a JSON object (no markdown fences):
{{
  "findings": [
    {{
      "severity": "high|medium|low",
      "category": "code_quality|performance|architecture|test_impact|documentation",
      "title": "Short specific title (5-10 words)",
      "line": <line_number>,
      "code_snippet": "exact problematic code",
      "description": "What's wrong and why it matters (1-2 sentences)",
      "suggested_fix": "Concrete fix (1 sentence)",
      "confidence": "high|medium|low"
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

Confidence guide:
- high: Clear violation, would tell a junior to fix
- medium: Likely an issue, depends on context
- low: Style/preference, might be intentional
"""


def _extract_added_lines(patch: str) -> str:
    """Extract lines added in a patch."""
    lines = []
    file_line = 0
    in_hunk = False
    for line in patch.split("\n"):
        if line.startswith("@@"):
            in_hunk = True
            continue
        if in_hunk and line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
    return "\n".join(lines)


"""
Layers 2-6: AI-powered analysis using Gemini.
Now sends full file context alongside the diff for better understanding.
"""
import re
from typing import List, Dict, Any

from review_agent.pattern_scanner import Finding, Severity
from shared.gemini_client import get_gemini_client
from shared.logger import get_logger

logger = get_logger(__name__)


AI_REVIEW_PROMPT = """You are a senior code reviewer analyzing a pull request diff.
Be CRITICAL but ACCURATE. Only report REAL issues.

IMPORTANT RULES:
1. DO NOT report security issues (hardcoded secrets, SQL injection, eval, etc.) - those are handled separately by a regex scanner.
2. Focus on CODE QUALITY, PERFORMANCE, ARCHITECTURE, TEST IMPACT, and DOCUMENTATION only.
3. Avoid duplicates: report each unique issue ONCE.
4. Be specific: cite exact line numbers and quote the problematic code.
5. For each finding, also rate your CONFIDENCE (high/medium/low) in whether it's actually an issue.

WHAT TO ANALYZE:

CODE QUALITY:
- Functions over 30 lines
- Deep nesting (more than 3 levels)
- Poor variable names (single chars; generic like data, temp, result)
- Magic numbers without named constants
- Missing error handling (no try/catch, swallowed errors)
- Functions doing multiple things
- Commented-out code

PERFORMANCE:
- N+1 queries (DB calls inside loops)
- Missing pagination
- Synchronous I/O blocking async code
- Memory leaks

ARCHITECTURE:
- Business logic in route handlers
- REST violations (wrong HTTP verbs)
- Wrong HTTP status codes
- Hardcoded URLs, ports, environment-specific values

TEST IMPACT:
- New functions without tests (high priority for critical paths)
- Modified signatures that would break existing tests

DOCUMENTATION:
- Missing JSDoc/docstrings on exported functions
- TODO/FIXME/HACK markers
- Complex logic without explanatory comments

FILE CONTEXT (for understanding only):
{file_context}

CHANGES TO REVIEW (with line numbers):
{code_to_review}

FILE: {filename}

Return ONLY a JSON object (no markdown fences):
{{
  "findings": [
    {{
      "severity": "high|medium|low",
      "category": "code_quality|performance|architecture|test_impact|documentation",
      "title": "Short specific title (5-10 words)",
      "line": <line_number>,
      "code_snippet": "exact problematic code",
      "description": "What's wrong and why it matters (1-2 sentences)",
      "suggested_fix": "Concrete fix (1 sentence)",
      "confidence": "high|medium|low"
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

Confidence guide:
- high: Clear violation, would tell a junior to fix
- medium: Likely an issue, depends on context
- low: Style/preference, might be intentional
"""


def _extract_added_lines(patch: str) -> str:
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


def _extract_all_lines(patch: str) -> str:
    """Extract complete file content from a patch (added + context lines)."""
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
        if line.startswith("+") or line.startswith(" "):
            file_line += 1
            content = line[1:] if line[0] in "+ " else line
            lines.append(f"{file_line}: {content}")
    return "\n".join(lines)


async def run_ai_analysis(filename: str, patch: str, pipeline_id: str) -> Dict[str, Any]:
    code_with_lines = _extract_added_lines(patch)
    file_context = _extract_all_lines(patch)

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

    # Truncate context if too long (Gemini has token limits)
    if len(file_context) > 8000:
        file_context = file_context[:8000] + "\n... (truncated)"

    prompt = AI_REVIEW_PROMPT.format(
        code_to_review=code_with_lines,
        file_context=file_context,
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

            # Skip low-confidence findings to reduce noise
            confidence = f.get("confidence", "high").lower()
            if confidence == "low":
                continue

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
            f"{len(findings)} findings (after confidence filter)"
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
