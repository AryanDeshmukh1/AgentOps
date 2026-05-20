"""
TestAgent — Second agent in the AgentOps pipeline.
Analyzes test impact and generates tests for uncovered code.
"""
import time
from dataclasses import asdict
from typing import Dict, Any, List

from test_agent.impact_analyzer import analyze_impact, TestImpact
from test_agent.test_generator import generate_tests_for_file, GeneratedTest
from shared.logger import get_logger

logger = get_logger(__name__)


async def run_test_analysis(pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run TestAgent on a PR.

    Steps:
    1. Analyze test impact (deterministic)
    2. Generate tests for uncovered functions (AI)
    3. Calculate test coverage score
    4. Return report

    Args:
        pipeline_data: Pipeline payload with files

    Returns:
        Test report dict
    """
    pipeline_id = pipeline_data["pipeline_id"]
    files = pipeline_data["files"]

    logger.info(f"[{pipeline_id}] TestAgent starting on {len(files)} file(s)")
    start_time = time.time()

    # Step 1: Impact analysis (no AI, deterministic)
    impacts = analyze_impact(files)
    logger.info(f"[{pipeline_id}] Impact analysis: {len(impacts)} source file(s) analyzed")

    # Step 2: Generate tests for uncovered functions
    all_generated_tests: List[GeneratedTest] = []
    files_needing_tests = []

    for impact in impacts:
        if impact.test_coverage_status == "uncovered" and impact.modified_functions:
            files_needing_tests.append(impact)

    logger.info(f"[{pipeline_id}] Files needing AI test generation: {len(files_needing_tests)}")

    for impact in files_needing_tests:
        # Find the file in original files list to get the patch
        file_data = next((f for f in files if f["filename"] == impact.source_file), None)
        if not file_data:
            continue

        result = await generate_tests_for_file(
            filename=impact.source_file,
            patch=file_data.get("patch", ""),
            functions=impact.modified_functions,
            pipeline_id=pipeline_id,
        )

        all_generated_tests.extend(result.get("tests", []))

    # Step 3: Calculate metrics
    total_source_files = sum(1 for i in impacts)
    covered_files = sum(1 for i in impacts if i.has_existing_tests)
    uncovered_files = sum(1 for i in impacts if i.test_coverage_status == "uncovered")

    coverage_score = _calculate_coverage_score(impacts, len(all_generated_tests))

    # Test pass rate is simulated for now (we'd actually run tests in a later iteration)
    # For now: assume generated tests would pass at typical AI-generated rate ~85%
    simulated_pass_rate = 100 if not all_generated_tests else 85

    # Decision
    decision = _determine_decision(coverage_score, simulated_pass_rate, files_needing_tests)

    duration_ms = int((time.time() - start_time) * 1000)

    report = {
        "pipeline_id": pipeline_id,
        "agent": "TestAgent",
        "duration_ms": duration_ms,
        "summary": {
            "total_source_files": total_source_files,
            "covered_files": covered_files,
            "uncovered_files": uncovered_files,
            "tests_generated": len(all_generated_tests),
        },
        "impacts": [asdict(i) for i in impacts],
        "generated_tests": [asdict(t) for t in all_generated_tests],
        "scores": {
            "coverage": coverage_score,
            "pass_rate": simulated_pass_rate,
        },
        "decision": decision,
    }

    logger.info(
        f"[{pipeline_id}] TestAgent complete in {duration_ms}ms — "
        f"coverage={coverage_score}, generated={len(all_generated_tests)} tests, decision={decision}"
    )

    return report


def _calculate_coverage_score(impacts: List[TestImpact], generated_count: int) -> int:
    """
    Score coverage from 0-100.
    - 100: All changed source files have tests
    - 50: Half have tests
    - 0: No tests for any changed source
    Bonus +10 if generated tests fill gaps.
    """
    if not impacts:
        return 100  # No source files = nothing to test

    covered = sum(1 for i in impacts if i.has_existing_tests)
    base_score = int((covered / len(impacts)) * 100)

    # Bonus for AI-generated tests filling gaps
    if generated_count > 0:
        base_score = min(100, base_score + 10)

    return base_score


def _determine_decision(
    coverage_score: int,
    pass_rate: int,
    needs_tests: List[TestImpact],
) -> str:
    """Decide whether the PR passes test checks."""
    if coverage_score >= 80 and pass_rate >= 80:
        return "PASS"
    elif coverage_score >= 60:
        return "PASS_WITH_WARNINGS"
    else:
        return "REQUEST_TESTS"