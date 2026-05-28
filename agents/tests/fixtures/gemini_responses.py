"""
Canned Gemini responses for integration tests. Real Gemini calls are never
made during testing; these fixtures replay realistic shapes.
"""

# Review agent's per-file AI analysis: 2 critical security findings
REVIEW_AI_CRITICAL = {
    "findings": [
        {
            "category": "security",
            "severity": "critical",
            "title": "Hardcoded API key",
            "description": "An API key is committed to source.",
            "file": "src/utils.py",
            "line": 5,
            "confidence": 0.95,
        },
        {
            "category": "security",
            "severity": "critical",
            "title": "SQL injection",
            "description": "User input concatenated into SQL string.",
            "file": "src/utils.py",
            "line": 12,
            "confidence": 0.90,
        },
    ]
}

# Review agent's per-file AI analysis: clean code, no findings
REVIEW_AI_CLEAN = {"findings": []}

# Test agent: requests tests
TEST_AGENT_REQUEST_TESTS = {
    "decision": "REQUEST_TESTS",
    "missing_test_files": ["tests/test_utils.py"],
    "suggested_tests": [
        {"file": "tests/test_utils.py", "name": "test_add", "rationale": "Tests new add()"},
    ],
}

# Test agent: clean (no tests needed)
TEST_AGENT_CLEAN = {
    "decision": "PASS",
    "missing_test_files": [],
    "suggested_tests": [],
}

# IncidentAgent root cause AI response
ROOT_CAUSE_AI_RESPONSE = {
    "root_cause": "The recent deployment introduced a regression causing simultaneous error rate and latency spikes.",
    "suggested_fix": "Rollback the deployment and investigate recent code changes.",
    "confidence": "high",
    "investigation_hints": [
        "Review code diff for the deployment commit",
        "Check database query performance metrics",
        "Examine service logs for new error patterns",
    ],
}