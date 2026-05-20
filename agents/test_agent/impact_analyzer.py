"""
Test Impact Analyzer — deterministic mapping of code changes to test files.
Identifies which existing tests are likely affected by a PR.
"""
import re
from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import PurePosixPath

from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TestImpact:
    """Represents how a code file impacts the test suite."""
    source_file: str
    related_test_files: List[str]
    modified_functions: List[str]
    has_existing_tests: bool
    test_coverage_status: str  # "covered" | "partial" | "uncovered"


# Common test file naming patterns
TEST_FILE_PATTERNS = [
    "{name}.test.{ext}",     # foo.test.js
    "{name}.spec.{ext}",     # foo.spec.js
    "test_{name}.{ext}",     # test_foo.py
    "{name}_test.{ext}",     # foo_test.py
    "tests/{name}.{ext}",    # tests/foo.js
    "__tests__/{name}.{ext}", # __tests__/foo.js
]


def extract_function_signatures(content: str, filename: str) -> List[str]:
    """Extract function/method/class names from source code."""
    functions = []

    # JavaScript/TypeScript patterns
    if filename.endswith(('.js', '.jsx', '.ts', '.tsx', '.mjs')):
        # function foo(...) {}
        functions += re.findall(r'function\s+([a-zA-Z_$][\w$]*)\s*\(', content)
        # const foo = () => / const foo = function
        functions += re.findall(r'(?:const|let|var)\s+([a-zA-Z_$][\w$]*)\s*=\s*(?:async\s+)?(?:function|\()', content)
        # class Foo { method() {} }
        functions += re.findall(r'class\s+([a-zA-Z_$][\w$]*)', content)
        # export function foo / export class Foo
        functions += re.findall(r'export\s+(?:async\s+)?(?:function|class)\s+([a-zA-Z_$][\w$]*)', content)

    # Python patterns
    elif filename.endswith('.py'):
        functions += re.findall(r'def\s+([a-zA-Z_][\w]*)\s*\(', content)
        functions += re.findall(r'class\s+([a-zA-Z_][\w]*)', content)
        functions += re.findall(r'async\s+def\s+([a-zA-Z_][\w]*)\s*\(', content)

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for f in functions:
        if f not in seen and not f.startswith('_'):  # Skip private functions
            seen.add(f)
            unique.append(f)

    return unique


def extract_added_functions(patch: str, filename: str) -> List[str]:
    """Extract function names that were ADDED (not modified) in the diff."""
    if not patch:
        return []

    # Get only added lines (start with '+')
    added_lines = []
    for line in patch.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            added_lines.append(line[1:])

    added_content = '\n'.join(added_lines)
    return extract_function_signatures(added_content, filename)


def find_related_test_files(source_file: str, all_files: List[str]) -> List[str]:
    """
    Given a source file like 'src/utils/auth.js',
    find test files like 'src/utils/auth.test.js' or 'tests/auth.test.js'.
    """
    related = []
    path = PurePosixPath(source_file)
    name = path.stem  # 'auth' from 'auth.js'
    ext = path.suffix.lstrip('.')  # 'js' from 'auth.js'

    # Generate possible test file paths
    candidates = set()
    for pattern in TEST_FILE_PATTERNS:
        # Try same directory
        candidates.add(str(path.parent / pattern.format(name=name, ext=ext)))
        # Try root tests folder
        candidates.add(pattern.format(name=name, ext=ext))

    # Also any file with the source name in a test path
    for f in all_files:
        if name in f and ('test' in f.lower() or 'spec' in f.lower()):
            related.append(f)
        elif f in candidates:
            related.append(f)

    return list(set(related))  # Remove duplicates


def analyze_impact(files: List[Dict[str, Any]]) -> List[TestImpact]:
    """
    Analyze test impact for all changed files in a PR.

    Args:
        files: List of file dicts from the PR (with filename, patch, etc.)

    Returns:
        List of TestImpact objects
    """
    impacts = []
    all_filenames = [f["filename"] for f in files]

    # Classify files
    source_files = [f for f in files if _is_source_file(f["filename"])]
    test_files = [f for f in files if _is_test_file(f["filename"])]

    test_filenames = [f["filename"] for f in test_files]

    for src in source_files:
        filename = src["filename"]
        patch = src.get("patch", "")

        # Find related test files (changed in this PR OR existing in repo paths)
        related = find_related_test_files(filename, all_filenames)
        # Filter to ones we have evidence exist (in the PR or matching naming)
        related = [r for r in related if r != filename]

        # Extract functions that were added/modified
        modified_funcs = extract_added_functions(patch, filename)

        # Determine coverage status
        if related:
            coverage_status = "covered"  # Has tests in same PR or naming match
        elif modified_funcs:
            coverage_status = "uncovered"  # New code, no test files found
        else:
            coverage_status = "partial"

        impacts.append(TestImpact(
            source_file=filename,
            related_test_files=related,
            modified_functions=modified_funcs,
            has_existing_tests=len(related) > 0,
            test_coverage_status=coverage_status,
        ))

    return impacts


def _is_source_file(filename: str) -> bool:
    """Is this a source code file (not a test)?"""
    if _is_test_file(filename):
        return False
    code_exts = ('.js', '.jsx', '.ts', '.tsx', '.mjs', '.py', '.java', '.go', '.rb', '.php', '.cs', '.cpp', '.rs')
    return filename.endswith(code_exts)


def _is_test_file(filename: str) -> bool:
    """Is this a test file?"""
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