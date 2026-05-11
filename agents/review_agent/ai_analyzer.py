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
Analyze the code across 5 dimensions and return ONLY a JSON response.

CODE QUALITY:
- Functions over 30 lines
- Deep nesting (more than 3 levels)
- Poor variable names (single chars, generic names)
- Magic numbers without explanation
- Missing error handling
- Console.log statements left in production code
- Commented-out dead code

PERFORMANCE ANTI-PATTERNS:
- N+1 query problems
- Missing pagination
- Synchronous I/O in async contexts
- Memory leaks
- Missing caching

ARCHITECTURE COMPLIANCE:
- Business logic in route handlers
- REST convention violations
- Hardcoded configuration
- Wrong HTTP status codes

TEST IMPACT:
- New code without tests
- Modified function signatures
- Removed tests
- Untestable code

DOCUMENTATION:
- Missing JSDoc/docstrings
- Outdated comments
- TODO/FIXME markers

CODE TO REVIEW:
```
{code_to_review}
```

FILE: {filename}

Return ONLY a JSON object in this exact format:
{{
  "findings": [
    {{
      "severity": "critical|high|medium|low",
      "category": "code_quality|performance|architecture|test_impact|documentation",
      "title": "Short descriptive title",
      "line": <line_number>,
      "code_snippet": "the problematic code",
      "description": "Detailed explanation",
      "suggested_fix": "How to fix it"
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
