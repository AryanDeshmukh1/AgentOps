"""
AgentOps Pipeline Orchestrator using LangGraph.

Defines the state machine that routes PRs through:
  webhook -> ReviewAgent -> [BLOCK or continue] -> TestAgent -> END

Each node is an async function that takes/returns PipelineState.
Edges decide where to go next based on state.
"""
from typing import TypedDict, List, Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END

from review_agent.agent import run_review
from test_agent.agent import run_test_analysis
from shared.logger import get_logger
from shared.dynamodb_service import get_dynamodb_service

logger = get_logger(__name__)


# ============================================================
# Pipeline State
# ============================================================

class PipelineState(TypedDict):
    """
    State that flows through the pipeline graph.
    Each agent reads and updates parts of this.
    """
    # Input (set when pipeline starts)
    pipeline_id: str
    repo: str
    pr_number: int
    pr_title: str
    pr_author: str
    head_sha: str
    base_sha: str
    files: List[Dict[str, Any]]
    timestamp: str

    # Filled in by agents as they run
    review_report: Optional[Dict[str, Any]]
    test_report: Optional[Dict[str, Any]]

    # Tracking
    current_agent: str
    status: str  # "running" | "blocked" | "complete" | "failed"
    final_decision: Optional[str]
    error: Optional[str]


# ============================================================
# Node Functions (each agent is a node)
# ============================================================

async def review_node(state: PipelineState) -> PipelineState:
    """Run ReviewAgent and update state."""
    pipeline_id = state["pipeline_id"]
    logger.info(f"[GRAPH] Entering review_node for {pipeline_id}")

    pipeline_data = {
        "pipeline_id": state["pipeline_id"],
        "repo": state["repo"],
        "pr_number": state["pr_number"],
        "pr_title": state["pr_title"],
        "pr_author": state["pr_author"],
        "head_sha": state["head_sha"],
        "base_sha": state["base_sha"],
        "files": state["files"],
        "timestamp": state["timestamp"],
    }

    try:
        report = await run_review(pipeline_data)

        # Persist to DynamoDB
        db = get_dynamodb_service()
        await db.save_agent_decision(pipeline_id, "ReviewAgent", report)

        return {
            **state,
            "review_report": report,
            "current_agent": "ReviewAgent",
            "final_decision": report["decision"],
        }
    except Exception as e:
        logger.error(f"[GRAPH] review_node failed: {e}", exc_info=True)
        return {
            **state,
            "status": "failed",
            "error": str(e),
        }


async def test_node(state: PipelineState) -> PipelineState:
    """Run TestAgent and update state."""
    pipeline_id = state["pipeline_id"]
    logger.info(f"[GRAPH] Entering test_node for {pipeline_id}")

    pipeline_data = {
        "pipeline_id": state["pipeline_id"],
        "repo": state["repo"],
        "pr_number": state["pr_number"],
        "files": state["files"],
    }

    try:
        report = await run_test_analysis(pipeline_data)

        db = get_dynamodb_service()
        await db.save_agent_decision(pipeline_id, "TestAgent", report)

        # If TestAgent requests changes, downgrade the final decision
        final_decision = state.get("final_decision", "PASS")
        if report["decision"] == "REQUEST_TESTS":
            final_decision = "REQUEST_CHANGES"

        return {
            **state,
            "test_report": report,
            "current_agent": "TestAgent",
            "final_decision": final_decision,
        }
    except Exception as e:
        logger.error(f"[GRAPH] test_node failed: {e}", exc_info=True)
        return {
            **state,
            "status": "failed",
            "error": str(e),
        }


async def finalize_node(state: PipelineState) -> PipelineState:
    """Mark pipeline as complete and persist final state."""
    pipeline_id = state["pipeline_id"]
    logger.info(f"[GRAPH] Entering finalize_node for {pipeline_id}")

    final_decision = state.get("final_decision", "UNKNOWN")
    status = "blocked" if final_decision == "BLOCK" else "complete"

    db = get_dynamodb_service()

    updates = {
        "status": status,
        "decision": final_decision,
        "current_agent": "complete",
    }

    review = state.get("review_report")
    if review:
        updates["review_score"] = review["scores"]["overall"]
        updates["total_findings"] = sum(review["summary"].values())

    test = state.get("test_report")
    if test:
        updates["coverage_score"] = test["scores"]["coverage"]

    await db.update_pipeline_status(pipeline_id, state["timestamp"], updates)

    return {
        **state,
        "status": status,
        "current_agent": "complete",
    }


# ============================================================
# Edge Functions (conditional routing)
# ============================================================

def route_after_review(state: PipelineState) -> Literal["test", "finalize"]:
    """
    After ReviewAgent runs, decide where to go next.
    - BLOCK -> skip tests, go straight to finalize
    - Anything else -> run TestAgent
    """
    review = state.get("review_report")
    if not review:
        return "finalize"

    if review["decision"] == "BLOCK":
        logger.info(f"[GRAPH] Routing: BLOCK -> finalize (skipping TestAgent)")
        return "finalize"

    logger.info(f"[GRAPH] Routing: PASS -> test")
    return "test"


# ============================================================
# Build the Graph
# ============================================================

def build_pipeline_graph():
    """Build and compile the AgentOps pipeline state graph."""
    graph = StateGraph(PipelineState)

    # Add nodes
    graph.add_node("review", review_node)
    graph.add_node("test", test_node)
    graph.add_node("finalize", finalize_node)

    # Set entry point
    graph.set_entry_point("review")

    # Conditional edge from review
    graph.add_conditional_edges(
        "review",
        route_after_review,
        {
            "test": "test",
            "finalize": "finalize",
        },
    )

    # test always goes to finalize
    graph.add_edge("test", "finalize")

    # finalize ends the pipeline
    graph.add_edge("finalize", END)

    return graph.compile()


# Singleton compiled graph
_compiled_graph = None


def get_pipeline_graph():
    """Get the compiled pipeline graph (cached)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_pipeline_graph()
        logger.info("[GRAPH] Pipeline graph compiled")
    return _compiled_graph


async def run_pipeline(pipeline_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the full pipeline through the LangGraph state machine.

    Args:
        pipeline_data: PR data from the webhook

    Returns:
        Final pipeline state with review_report, test_report, etc.
    """
    initial_state: PipelineState = {
        "pipeline_id": pipeline_data["pipeline_id"],
        "repo": pipeline_data["repo"],
        "pr_number": pipeline_data["pr_number"],
        "pr_title": pipeline_data["pr_title"],
        "pr_author": pipeline_data["pr_author"],
        "head_sha": pipeline_data["head_sha"],
        "base_sha": pipeline_data["base_sha"],
        "files": pipeline_data["files"],
        "timestamp": pipeline_data["timestamp"],
        "review_report": None,
        "test_report": None,
        "current_agent": "starting",
        "status": "running",
        "final_decision": None,
        "error": None,
    }

    graph = get_pipeline_graph()
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        f"[GRAPH] Pipeline complete: {pipeline_data['pipeline_id']} "
        f"final_decision={final_state.get('final_decision')} "
        f"status={final_state.get('status')}"
    )

    return final_state
