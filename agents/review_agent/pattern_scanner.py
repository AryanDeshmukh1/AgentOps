"""
Layer 1: Deterministic regex-based pattern scanner.
Catches obvious security vulnerabilities and code smells without AI.
Runs in milliseconds and is the first line of defense.
"""
import re
from dataclasses import dataclass
from typing import List
from enum import Enum

from shared.logger import get_logger

logger = get_logger(__name__)


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Finding:
    """Represents a single issue found in code."""
    severity: Severity
    category: str
    title: str
    file: str
    line: int
    code_snippet: str
    description: str
    suggested_fix: str
    detection_method: str = "regex"


# ============================================================
# Pattern Definitions
# ============================================================

# Each entry: (pattern, severity, category, title, description, fix)
SECURITY_PATTERNS = [
    # === Hardcoded Secrets ===
    (
        r'(?i)(api[_-]?key|apikey)\s*[:=]\s*["\']([A-Za-z0-9+/=_\-]{20,})["\']',
        Severity.CRITICAL,
        "A02:2025 - Cryptographic Failures",
        "Hardcoded API key",
        "API key embedded in source code can be extracted by anyone with access to the codebase or git history.",
        "Move the key to an environment variable: process.env.API_KEY or os.getenv('API_KEY')",
    ),
    (
        r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']([^"\']{6,})["\']',
        Severity.CRITICAL,
        "A02:2025 - Cryptographic Failures",
        "Hardcoded password",
        "Plaintext password in source code is a critical security risk and likely violates compliance requirements.",
        "Use environment variables or a secrets manager (AWS Secrets Manager, HashiCorp Vault).",
    ),
    (
        r'(?i)(secret|token)\s*[:=]\s*["\']([A-Za-z0-9+/=_\-]{20,})["\']',
        Severity.CRITICAL,
        "A02:2025 - Cryptographic Failures",
        "Hardcoded secret/token",
        "Secret tokens (JWT secrets, encryption keys) in code can be exfiltrated via repository access.",
        "Store in environment variables and rotate immediately if this code was ever pushed.",
    ),
    (
        r'(AKIA|ASIA)[A-Z0-9]{16}',
        Severity.CRITICAL,
        "A02:2025 - Cryptographic Failures",
        "AWS access key in code",
        "AWS access keys grant full access to AWS resources. If pushed to GitHub, AWS auto-detects and notifies, but attackers act fast.",
        "Revoke the key immediately in AWS IAM console, rotate, and use IAM roles or environment variables.",
    ),
    (
        r'sk-[a-zA-Z0-9]{32,}',
        Severity.CRITICAL,
        "A02:2025 - Cryptographic Failures",
        "OpenAI/API SK key",
        "Service-key style tokens (sk-xxx) are typically API keys for paid services. Exposure could cost real money.",
        "Revoke the key in the provider's dashboard and load from environment variables.",
    ),
    (
        r'ghp_[a-zA-Z0-9]{36}',
        Severity.CRITICAL,
        "A02:2025 - Cryptographic Failures",
        "GitHub personal access token",
        "GitHub PAT tokens can read/write repositories. Exposure allows attackers to modify code.",
        "Revoke at github.com/settings/tokens and use a GitHub App with scoped permissions instead.",
    ),
    (
        r'-----BEGIN (RSA |EC |DSA |OPENSSH |)PRIVATE KEY-----',
        Severity.CRITICAL,
        "A02:2025 - Cryptographic Failures",
        "Private key embedded in source",
        "Private keys (SSH, SSL, signing keys) in source code are catastrophic if leaked.",
        "Remove immediately, rotate the key, and store in a secrets manager. Audit git history for prior commits.",
    ),

    # === Dangerous Functions (Code Injection) ===
    (
        r'\beval\s*\(',
        Severity.HIGH,
        "A05:2025 - Injection",
        "Use of eval()",
        "eval() executes arbitrary code and is a major attack vector if user input reaches it.",
        "Use JSON.parse() for data, or refactor to avoid dynamic code execution entirely.",
    ),
    (
        r'\.innerHTML\s*=',
        Severity.HIGH,
        "A05:2025 - Injection",
        "innerHTML assignment",
        "Setting innerHTML with user-controlled data enables XSS attacks.",
        "Use textContent for plain text, or sanitize HTML with DOMPurify if HTML is required.",
    ),
    (
        r'dangerouslySetInnerHTML',
        Severity.HIGH,
        "A05:2025 - Injection",
        "React dangerouslySetInnerHTML",
        "React's dangerouslySetInnerHTML bypasses XSS protection. Risky if data isn't sanitized.",
        "Render content as text where possible, or sanitize with DOMPurify before passing.",
    ),
    (
        r'(?:child_process\.)?exec(?:Sync)?\s*\(',
        Severity.HIGH,
        "A05:2025 - Injection",
        "OS command execution",
        "exec() runs shell commands. With user input, this enables command injection attacks.",
        "Use execFile() with argument arrays instead of exec() with concatenated strings.",
    ),
    (
        r'document\.write\s*\(',
        Severity.MEDIUM,
        "A05:2025 - Injection",
        "document.write()",
        "document.write() can be exploited for XSS and is deprecated in modern browsers.",
        "Use DOM manipulation methods like createElement and appendChild.",
    ),

    # === SQL/NoSQL Injection ===
    (
        r'(?:SELECT|INSERT|UPDATE|DELETE)[^;]*?["\']?\s*\+\s*\w+',
        Severity.HIGH,
        "A05:2025 - Injection",
        "Possible SQL injection (string concatenation in query)",
        "Concatenating user input into SQL queries is the textbook SQL injection vulnerability.",
        "Use parameterized queries: db.query('SELECT * FROM users WHERE id = ?', [userId])",
    ),
    (
        r'\.find\s*\(\s*\{[^}]*req\.(body|query|params)',
        Severity.HIGH,
        "A05:2025 - Injection",
        "Possible NoSQL injection (unsanitized query)",
        "Passing user input directly to MongoDB queries allows operator injection like {$gt: ''}.",
        "Sanitize with mongo-sanitize, or explicitly cast inputs to expected types.",
    ),

    # === Misconfiguration ===
    (
        r'Access-Control-Allow-Origin["\']?\s*[,:]\s*["\']?\*',
        Severity.MEDIUM,
        "A05:2025 - Security Misconfiguration",
        "Wildcard CORS policy",
        "CORS allowing any origin (*) opens APIs to attacks from arbitrary websites.",
        "Specify exact allowed origins from a whitelist, or use credentials-based dynamic origins.",
    ),
    (
        r'console\.log\s*\([^)]*(?:password|token|secret|key|api[_-]?key)',
        Severity.MEDIUM,
        "A09:2025 - Logging Failures",
        "Sensitive data in console.log",
        "Logging credentials exposes them in log files which may be archived or accessed by others.",
        "Remove the log, or redact sensitive fields before logging.",
    ),

    # === Code Quality (Low severity) ===
    (
        r'^[\s]*console\.log\s*\(',
        Severity.LOW,
        "Code Quality",
        "console.log in code",
        "console.log statements should not appear in production code.",
        "Remove or replace with a proper logger (winston, pino).",
    ),
    (
        r'(?://|#)\s*(TODO|FIXME|HACK|XXX)',
        Severity.LOW,
        "Code Quality",
        "TODO/FIXME comment",
        "Temporary code markers indicate incomplete work shipped to production.",
        "Resolve the TODO or create a tracked issue and remove the comment.",
    ),
]


def scan_file(filename: str, content: str) -> List[Finding]:
    """
    Scan a single file's content against all patterns.

    Args:
        filename: Path of the file (for reporting)
        content: Full text content of the file

    Returns:
        List of Finding objects
    """
    findings: List[Finding] = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, start=1):
        # Skip very long lines (likely minified)
        if len(line) > 500:
            continue

        for pattern, severity, category, title, description, fix in SECURITY_PATTERNS:
            match = re.search(pattern, line)
            if match:
                findings.append(Finding(
                    severity=severity,
                    category=category,
                    title=title,
                    file=filename,
                    line=line_num,
                    code_snippet=line.strip()[:200],
                    description=description,
                    suggested_fix=fix,
                ))

    return findings


def scan_patch(filename: str, patch: str) -> List[Finding]:
    """
    Scan only the lines added in a PR patch (lines starting with '+').
    This focuses analysis on changes the developer made, not pre-existing code.
    """
    findings: List[Finding] = []
    if not patch:
        return findings

    current_new_line = 0
    in_hunk = False

    for line in patch.split("\n"):
        # Hunk header: @@ -old_start,old_count +new_start,new_count @@
        if line.startswith("@@"):
            match = re.search(r'\+(\d+)', line)
            if match:
                current_new_line = int(match.group(1)) - 1
                in_hunk = True
            continue

        # File metadata lines (--- a/file, +++ b/file) — skip
        if line.startswith("---") or line.startswith("+++"):
            continue

        # If we haven't seen a hunk header yet but have content, assume line 1
        if not in_hunk and (line.startswith("+") or line.startswith(" ") or line.startswith("-")):
            in_hunk = True
            current_new_line = 0

        # Added line: starts with '+' but not '+++'
        if line.startswith("+"):
            current_new_line += 1
            added_content = line[1:]  # Strip leading '+'

            for pattern, severity, category, title, description, fix in SECURITY_PATTERNS:
                if re.search(pattern, added_content):
                    findings.append(Finding(
                        severity=severity,
                        category=category,
                        title=title,
                        file=filename,
                        line=current_new_line,
                        code_snippet=added_content.strip()[:200],
                        description=description,
                        suggested_fix=fix,
                    ))
        # Context line (unchanged): starts with space
        elif line.startswith(" "):
            current_new_line += 1
        # Removed lines start with '-' but don't advance new line counter

    return findings