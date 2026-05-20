"""
AI-powered test generator using Gemini.
"""
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from shared.gemini_client import get_gemini_client
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GeneratedTest:
    name: str
    category: str
    description: str
    target_function: str
    code: str


TEST_GEN_PROMPT = """You are a senior QA engineer generating unit tests.

CODE TO TEST:
{code_to_test}

FILE: {filename}
FRAMEWORK: {framework}

FUNCTIONS THAT NEED TESTS:
{functions}

Generate 3-5 test cases per function covering happy path, edge cases, and error cases.

Return ONLY a JSON object:
{{
  "tests": [
    {{
      "name": "test name",
      "category": "happy_path",
      "target_function": "fn name",
      "description": "what it tests",
      "code": "the test code"
    }}
  ],
  "framework_used": "{framework}"
}}
"""


def detect_framework(filename: str) -> str:
    if filename.endswith(('.js', '.jsx', '.mjs', '.ts', '.tsx')):
        return "jest"
    elif filename.endswith('.py'):
        return "pytest"
    return "jest"


async def generate_tests_for_file(filename, patch, functions, pipeline_id):
    if not functions:
        return {"tests": [], "framework_used": detect_framework(filename)}

    added_lines = []
    for line in patch.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            added_lines.append(line[1:])
    code_to_test = '\n'.join(added_lines)

    if not code_to_test.strip():
        return {"tests": [], "framework_used": detect_framework(filename)}

    framework = detect_framework(filename)
    prompt = TEST_GEN_PROMPT.format(
        code_to_test=code_to_test,
        filename=filename,
        framework=framework,
        functions=", ".join(functions),
    )

    logger.info(f"[{pipeline_id}] Generating tests for {filename}")

    try:
        client = get_gemini_client()
        response = await client.generate_json(prompt, temperature=0.3)
        tests_raw = response.get("tests", [])
        tests = [
            GeneratedTest(
                name=t.get("name", "unnamed"),
                category=t.get("category", "happy_path"),
                description=t.get("description", ""),
                target_function=t.get("target_function", ""),
                code=t.get("code", ""),
            )
            for t in tests_raw if t.get("code")
        ]
        logger.info(f"[{pipeline_id}] Generated {len(tests)} tests")
        return {"tests": tests, "framework_used": framework}
    except Exception as e:
        logger.error(f"[{pipeline_id}] Test generation failed: {e}")
        return {"tests": [], "framework_used": framework, "error": str(e)}
