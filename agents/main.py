"""
AgentOps Agent System — FastAPI server hosting the multi-agent orchestrator.
Now powered by LangGraph state machine + approval background worker.
"""
import os
import asyncio
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agentops")

# How often the background worker scans for approvals to auto-promote/expire.
APPROVAL_WORKER_INTERVAL_SECONDS = int(os.getenv("APPROVAL_WORKER_INTERVAL", "60"))
METRIC_WORKER_INTERVAL_SECONDS = int(os.getenv("METRIC_WORKER_INTERVAL", "30"))


async def approval_worker():
    """
    Background task: scans pending approvals every N seconds.
    - SOFT approvals older than SOFT_AUTO_PROMOTE_MINUTES -> auto_promoted
    - HARD approvals older than HARD_EXPIRE_HOURS         -> expired
    Each transition is conditional (no double-write) and writes an audit event.
    """
    from shared.dynamodb_service import get_dynamodb_service
    from orchestrator.approval_state_machine import (
        should_auto_promote,
        should_expire,
        build_event,
        ApprovalState,
    )

    logger.info(f"[APPROVAL_WORKER] Started — interval={APPROVAL_WORKER_INTERVAL_SECONDS}s")
    db = get_dynamodb_service()

    while True:
        try:
            pending = await db.list_pending_approvals()
            if pending:
                logger.info(f"[APPROVAL_WORKER] Scanning {len(pending)} pending approval(s)")

            for approval in pending:
                approval_id = approval["approval_id"]
                pipeline_id = approval["pipeline_id"]
                from_state = approval.get("status", "pending")

                if should_auto_promote(approval):
                    ok = await db.transition_approval(
                        pipeline_id=pipeline_id,
                        approval_id=approval_id,
                        new_status=ApprovalState.AUTO_PROMOTED.value,
                        actor="system:auto_promote",
                        comment=f"SOFT approval auto-promoted after timeout",
                        expected_status=from_state,
                    )
                    if ok:
                        event = build_event(
                            approval_id=approval_id,
                            from_state=from_state,
                            to_state=ApprovalState.AUTO_PROMOTED.value,
                            actor="system:auto_promote",
                            comment="Timeout reached",
                        )
                        await db.save_approval_event(event)
                        logger.info(f"[APPROVAL_WORKER] Auto-promoted {approval_id}")

                elif should_expire(approval):
                    ok = await db.transition_approval(
                        pipeline_id=pipeline_id,
                        approval_id=approval_id,
                        new_status=ApprovalState.EXPIRED.value,
                        actor="system:expire",
                        comment="HARD approval expired without decision",
                        expected_status=from_state,
                    )
                    if ok:
                        event = build_event(
                            approval_id=approval_id,
                            from_state=from_state,
                            to_state=ApprovalState.EXPIRED.value,
                            actor="system:expire",
                            comment="Timeout reached",
                        )
                        await db.save_approval_event(event)
                        logger.info(f"[APPROVAL_WORKER] Expired {approval_id}")

        except Exception as e:
            logger.error(f"[APPROVAL_WORKER] Loop error: {e}", exc_info=True)

        await asyncio.sleep(APPROVAL_WORKER_INTERVAL_SECONDS)

async def metric_worker():
    """
    Background task: every N seconds, sample metrics for each promoted deployment,
    then run anomaly detection. Fires incidents to AgentOps-Incidents.
    """
    from shared.dynamodb_service import get_dynamodb_service
    from incident_agent.metric_collector import collect_one_sample
    from incident_agent.agent import evaluate_sample

    logger.info(f"[METRIC_WORKER] Started — interval={METRIC_WORKER_INTERVAL_SECONDS}s")
    db = get_dynamodb_service()

    while True:
        try:
            promoted = await db.list_promoted_deployments()
            if promoted:
                logger.info(f"[METRIC_WORKER] Sampling {len(promoted)} promoted deployment(s)")
            for deployment in promoted:
                deployment_id = deployment["deployment_id"]
                sample = await collect_one_sample(deployment_id)
                if sample:
                    await evaluate_sample(deployment_id, sample)
        except Exception as e:
            logger.error(f"[METRIC_WORKER] Loop error: {e}", exc_info=True)

        await asyncio.sleep(METRIC_WORKER_INTERVAL_SECONDS)
        
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AgentOps Agent System starting up...")
    logger.info(f"AWS Region: {os.getenv('AWS_REGION', 'not_set')}")
    logger.info(f"Gemini Model: {os.getenv('GEMINI_MODEL_PRIMARY', 'not_set')}")

    # Warm up the graph
    from orchestrator.graph import get_pipeline_graph
    get_pipeline_graph()

    # Start background approval worker
    approval_task = asyncio.create_task(approval_worker())
    metric_task = asyncio.create_task(metric_worker())

    yield

    logger.info("AgentOps Agent System shutting down...")
    approval_task.cancel()
    metric_task.cancel()
    for t in (approval_task, metric_task):
        try:
            await t
        except asyncio.CancelledError:
            pass
    logger.info("[WORKERS] Cancelled cleanly")

app = FastAPI(
    title="AgentOps Agent System",
    description="Multi-agent AI orchestrator powered by LangGraph",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:4000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"name": "AgentOps Agent System", "version": "0.2.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "agentops-agents"}


@app.get("/health/deep")
async def health_deep():
    return {"status": "healthy", "service": "agentops-agents"}


class FileChange(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    changes: int
    patch: Optional[str] = ""


class ReviewRequest(BaseModel):
    pipeline_id: str
    repo: str
    pr_number: int
    pr_title: str
    pr_author: str
    pr_body: Optional[str] = ""
    head_sha: str
    base_sha: str
    files: List[FileChange]
    timestamp: str


@app.post("/api/review")
async def receive_review_request(request: ReviewRequest):
    """
    Entry point for pipelines. Hands off to the LangGraph orchestrator.
    """
    logger.info("=" * 60)
    logger.info(f"NEW PIPELINE: {request.pipeline_id}")
    logger.info(f"  Repo: {request.repo}")
    logger.info(f"  PR #{request.pr_number}: {request.pr_title}")
    logger.info(f"  Files changed: {len(request.files)}")
    logger.info("=" * 60)

    pipeline_data = request.model_dump()

    from orchestrator.graph import run_pipeline
    from review_agent.github_formatter import format_combined_report
    from shared.dynamodb_service import get_dynamodb_service

    db = get_dynamodb_service()
    await db.save_pipeline(pipeline_data)

    try:
        final_state = await run_pipeline(pipeline_data)

        review_report = final_state.get("review_report")
        test_report = final_state.get("test_report")
        final_decision = final_state.get("final_decision", "UNKNOWN")

        logger.info("=" * 60)
        logger.info(f"PIPELINE COMPLETE: {request.pipeline_id}")
        logger.info(f"  Final Decision: {final_decision}")
        if review_report:
            logger.info(f"  Review Score: {review_report['scores']['overall']}/100")
        if test_report:
            logger.info(f"  Coverage Score: {test_report['scores']['coverage']}/100")
            logger.info(f"  Tests Generated: {test_report['summary']['tests_generated']}")
        logger.info("=" * 60)

        if review_report:
            comment_body = format_combined_report(review_report, test_report)
            backend_url = os.getenv("BACKEND_URL", "http://backend:4000")

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"{backend_url}/api/webhooks/post-review",
                        json={
                            "repo": request.repo,
                            "pr_number": request.pr_number,
                            "comment": comment_body,
                            "head_sha": request.head_sha,
                            "decision": final_decision,
                        },
                    )
                    if response.status_code == 200:
                        logger.info(f"[{request.pipeline_id}] Comment posted on GitHub")
                    else:
                        logger.warning(f"[{request.pipeline_id}] Comment post HTTP {response.status_code}")
            except Exception as post_err:
                logger.error(f"[{request.pipeline_id}] Comment post failed: {post_err}")

        return {
            "status": "completed",
            "pipeline_id": request.pipeline_id,
            "final_decision": final_decision,
            "review_report": review_report,
            "test_report": test_report,
        }

    except Exception as e:
        logger.error(f"[{request.pipeline_id}] Pipeline failed: {e}", exc_info=True)
        await db.update_pipeline_status(
            request.pipeline_id,
            request.timestamp,
            {"status": "failed", "error": str(e)[:500]},
        )
        return {"status": "error", "pipeline_id": request.pipeline_id, "error": str(e)}