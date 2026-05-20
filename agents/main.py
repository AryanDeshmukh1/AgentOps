"""
AgentOps Agent System — FastAPI server hosting the multi-agent orchestrator.
Now powered by LangGraph state machine.
"""
import os
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AgentOps Agent System starting up...")
    logger.info(f"AWS Region: {os.getenv('AWS_REGION', 'not_set')}")
    logger.info(f"Gemini Model: {os.getenv('GEMINI_MODEL_PRIMARY', 'not_set')}")
    # Warm up the graph
    from orchestrator.graph import get_pipeline_graph
    get_pipeline_graph()
    yield
    logger.info("AgentOps Agent System shutting down...")


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

    # Save initial pipeline record
    db = get_dynamodb_service()
    await db.save_pipeline(pipeline_data)

    try:
        # Run the LangGraph pipeline
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

        # Post combined comment to GitHub via backend
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
