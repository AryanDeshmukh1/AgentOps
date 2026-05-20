"""
Test Impact Analyzer — deterministic mapping of code changes to test files.
Now with smarter heuristics: detects existing test files from filenames
even when they're not in the current PR.
"""
import re
from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import PurePosixPath

from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TestImpact:
    source_file: str
    related_test_files: List[str]
    modified_functions: List[str]
    has_existing_tests: bool
    test_coverage_status: str  # "covered" | "partial" | "uncovered"
    is_critical_path: bool      # Files in auth/, payment/, security/, etc.


# Naming conventions for test files
def expected_test_paths(source_file: str) -> List[str]:
    """Given source/utils/auth.js, return likely test paths."""
    path = PurePosixPath(source_file)
    name = path.stem
    ext = path.suffix.lstrip('.')
    parent = path.parent

    paths = [
        f"{parent}/{name}.test.{ext}",
        f"{parent}/{name}.spec.{ext}",
        f"{parent}/__tests__/{name}.{ext}",
        f"{parent}/__tests__/{name}.test.{ext}",
        f"{parent}/tests/{name}.{ext}",
        f"tests/{name}.{ext}",
        f"tests/{name}.test.{ext}",
        f"test/{name}.{ext}",
        f"test_{name}.py",
        f"tests/test_{name}.py",
        f"{name}_test.go",
    ]
    return paths


def extract_function_signatures(content: str, filename: str) -> List[str]:
    """Extract function/method/class names from source code."""
    functions = []
    if filename.endswith(('.js', '.jsx', '.ts', '.tsx', '.mjs')):
        functions += re.findall(r'function\s+([a-zA-Z_$][\w$]*)\s*\(', content)
        functions += re.findall(r'(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function|\()', content)
        functions += re.findall(r'class\s+([a-zA-Z_$][\w$]*)', content)
        functions += re.findall(r'export\s+(?:async\s+)?(?:function|class)\s+([a-zA-Z_$][\w$]*)', content)
    elif filename.endswith('.py'):
        functions += re.findall(r'def\s+([a-zA-Z_][\w]*)\s*\(', content)
        functions += re.findall(r'class\s+([a-zA-Z_][\w]*)', content)
        functions += re.findall(r'async\s+def\s+([a-zA-Z_][\w]*)\s*\(', content)

    seen = set()
    unique = []
    for f in functions:
        if f not in seen and not f.startswith('_'):
            seen.add(f)
            unique.append(f)
    return unique


def extract_added_functions(patch: str, filename: str) -> List[str]:
    """Extract function names added in the diff."""
    if not patch:
        return []
    added_lines = []
    for line in patch.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            added_lines.append(line[1:])
    return extract_function_signatures('\n'.join(added_lines), filename)


def is_critical_path(filename: str) -> bool:
    """Files in critical paths require tests."""
    lower = filename.lower()
    critical_keywords = ['auth', 'security', 'payment', 'billing', 'crypto', 'admin', 'permission']
    return any(kw in lower for kw in critical_keywords)


def analyze_impact(files: List[Dict[str, Any]]) -> List[TestImpact]:
    """Analyze test impact for all changed files."""
    impacts = []
    all_filenames = [f["filename"] for f in files]

    source_files = [f for f in files if _is_source_file(f["filename"])]
    test_files_in_pr = [f["filename"] for f in files if _is_test_file(f["filename"])]

    for src in source_files:
        filename = src["filename"]
        patch = src.get("patch", "")

        # Look for related test files
        expected_paths = expected_test_paths(filename)
        related = []

        # Check if any test file in this PR matches expected paths
        for test_path in expected_paths:
            for tf in test_files_in_pr:
                if test_path == tf or PurePosixPath(tf).stem == PurePosixPath(filename).stem + ".test":
                    related.append(tf)

        # Also: any test file that mentions this source file's name
        src_name = PurePosixPath(filename).stem
        for tf in test_files_in_pr:
            if src_name in tf and tf not in related:
                related.append(tf)

        modified_funcs = extract_added_functions(patch, filename)
        critical = is_critical_path(filename)

        # Coverage logic:
        if related:
            coverage_status = "covered"
        elif not modified_funcs:
            # No new functions added — just minor changes, partial coverage
            coverage_status = "partial"
        elif critical:
            # Critical code with no tests = UNCOVERED (red flag)
            coverage_status = "uncovered"
        else:
            # Non-critical code without explicit test files
            coverage_status = "partial"

        impacts.append(TestImpact(
            source_file=filename,
            related_test_files=related,
            modified_functions=modified_funcs,
            has_existing_tests=len(related) > 0,
            test_coverage_status=coverage_status,
            is_critical_path=critical,
        ))

    return impacts


def _is_source_file(filename: str) -> bool:
    if _is_test_file(filename):
        return False
    code_exts = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.py', '.java', '.go', '.rb', '.php', '.cs', '.cpp', '.rs')
    return filename.endswith(code_exts)


def _is_test_file(filename: str) -> bool:
    name_lower = filename.lower()
    return (
        '.test.' in name_lower or
        '.spec.' in name_lower or
        '/test_' in name_lower or
        '_test.' in name_lower or
        '/tests/' in name_lower or
        '/__tests__/' in name_lower or
        name_lower.startswith('test_')
    )
