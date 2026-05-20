"""
AgentOps Pipeline Orchestrator using LangGraph with approval gateway.
"""
from typing import TypedDict, List, Dict, Any, Optional, Literal
from langgraph.graph import StateGraph, END

from review_agent.agent import run_review
from test_agent.agent import run_test_analysis
from orchestrator.risk_classifier import classify_risk
from shared.logger import get_logger
from shared.dynamodb_service import get_dynamodb_service

logger = get_logger(__name__)


class PipelineState(TypedDict):
    pipeline_id: str
    repo: str
    pr_number: int
    pr_title: str
    pr_author: str
    head_sha: str
    base_sha: str
    files: List[Dict[str, Any]]
    timestamp: str
    review_report: Optional[Dict[str, Any]]
    test_report: Optional[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    approval_id: Optional[str]
    current_agent: str
    status: str
    final_decision: Optional[str]
    error: Optional[str]


async def review_node(state):
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
        db = get_dynamodb_service()
        await db.save_agent_decision(pipeline_id, "ReviewAgent", report)
        return {**state, "review_report": report, "current_agent": "ReviewAgent", "final_decision": report["decision"]}
    except Exception as e:
        logger.error(f"[GRAPH] review_node failed: {e}", exc_info=True)
        return {**state, "status": "failed", "error": str(e)}


async def test_node(state):
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
        final_decision = state.get("final_decision", "PASS")
        if report["decision"] == "REQUEST_TESTS":
            final_decision = "REQUEST_CHANGES"
        return {**state, "test_report": report, "current_agent": "TestAgent", "final_decision": final_decision}
    except Exception as e:
        logger.error(f"[GRAPH] test_node failed: {e}", exc_info=True)
        return {**state, "status": "failed", "error": str(e)}


async def approval_node(state):
    pipeline_id = state["pipeline_id"]
    logger.info(f"[GRAPH] Entering approval_node for {pipeline_id}")
    risk = classify_risk(
        review_report=state.get("review_report"),
        test_report=state.get("test_report"),
        files=state.get("files", []),
    )
    logger.info(f"[GRAPH] Risk classified: {risk['risk_level']} - {risk['reason']}")
    db = get_dynamodb_service()
    if risk["requires_approval"]:
        review_summary = {
            "decision": state.get("review_report", {}).get("decision"),
            "score": state.get("review_report", {}).get("scores", {}).get("overall"),
            "findings": state.get("review_report", {}).get("summary"),
        }
        approval_id = await db.save_approval_request(pipeline_id, risk, review_summary)
        if risk["risk_level"] == "hard":
            return {**state, "risk_assessment": risk, "approval_id": approval_id, "current_agent": "ApprovalGate", "final_decision": "AWAITING_APPROVAL", "status": "awaiting_approval"}
        else:
            return {**state, "risk_assessment": risk, "approval_id": approval_id, "current_agent": "ApprovalGate"}
    else:
        return {**state, "risk_assessment": risk, "current_agent": "ApprovalGate"}


async def finalize_node(state):
    pipeline_id = state["pipeline_id"]
    logger.info(f"[GRAPH] Entering finalize_node for {pipeline_id}")
    final_decision = state.get("final_decision", "UNKNOWN")
    status_value = state.get("status", "complete")
    if status_value not in ("blocked", "awaiting_approval", "failed"):
        status_value = "blocked" if final_decision == "BLOCK" else "complete"
    db = get_dynamodb_service()
    updates = {"status": status_value, "decision": final_decision, "current_agent": "complete"}
    review = state.get("review_report")
    if review:
        updates["review_score"] = review["scores"]["overall"]
        updates["total_findings"] = sum(review["summary"].values())
    test = state.get("test_report")
    if test:
        updates["coverage_score"] = test["scores"]["coverage"]
    risk = state.get("risk_assessment")
    if risk:
        updates["risk_level"] = risk["risk_level"]
    await db.update_pipeline_status(pipeline_id, state["timestamp"], updates)
    return {**state, "status": status_value, "current_agent": "complete"}


def route_after_review(state) -> Literal["test", "finalize"]:
    review = state.get("review_report")
    if not review:
        return "finalize"
    if review["decision"] == "BLOCK":
        logger.info("[GRAPH] Routing: BLOCK -> finalize")
        return "finalize"
    logger.info("[GRAPH] Routing: PASS -> test")
    return "test"


def route_after_test(state) -> Literal["approval", "finalize"]:
    review = state.get("review_report", {})
    if review.get("decision") == "BLOCK":
        return "finalize"
    logger.info("[GRAPH] Routing: test -> approval gate")
    return "approval"


def build_pipeline_graph():
    graph = StateGraph(PipelineState)
    graph.add_node("review", review_node)
    graph.add_node("test", test_node)
    graph.add_node("approval", approval_node)
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("review")
    graph.add_conditional_edges("review", route_after_review, {"test": "test", "finalize": "finalize"})
    graph.add_conditional_edges("test", route_after_test, {"approval": "approval", "finalize": "finalize"})
    graph.add_edge("approval", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


_compiled_graph = None


def get_pipeline_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_pipeline_graph()
        logger.info("[GRAPH] Pipeline graph compiled with approval gateway")
    return _compiled_graph


async def run_pipeline(pipeline_data):
    initial_state = {
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
        "risk_assessment": None,
        "approval_id": None,
        "current_agent": "starting",
        "status": "running",
        "final_decision": None,
        "error": None,
    }
    graph = get_pipeline_graph()
    final_state = await graph.ainvoke(initial_state)
    logger.info(f"[GRAPH] Pipeline complete: {pipeline_data['pipeline_id']} final_decision={final_state.get('final_decision')} status={final_state.get('status')}")
    return final_state
