"""
AgentOps Agent System — FastAPI server hosting the multi-agent orchestrator.
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
    yield
    logger.info("AgentOps Agent System shutting down...")


app = FastAPI(
    title="AgentOps Agent System",
    description="Multi-agent AI orchestrator for CI/CD pipelines",
    version="0.1.0",
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
    return {"name": "AgentOps Agent System", "version": "0.1.0", "status": "running"}


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
    logger.info("=" * 60)
    logger.info(f"NEW PIPELINE: {request.pipeline_id}")
    logger.info(f"  Repo: {request.repo}")
    logger.info(f"  PR #{request.pr_number}: {request.pr_title}")
    logger.info(f"  Files changed: {len(request.files)}")
    logger.info("=" * 60)

    pipeline_data = request.model_dump()

    from review_agent.agent import run_review
    from review_agent.github_formatter import format_combined_report
    from test_agent.agent import run_test_analysis
    from shared.dynamodb_service import get_dynamodb_service

    db = get_dynamodb_service()
    await db.save_pipeline(pipeline_data)

    try:
        # ============ ReviewAgent ============
        review_report = await run_review(pipeline_data)

        logger.info(f"[REVIEW DONE] {request.pipeline_id} — decision={review_report['decision']}, score={review_report['scores']['overall']}")

        await db.save_agent_decision(request.pipeline_id, "ReviewAgent", review_report)

        # ============ TestAgent ============
        # Only run TestAgent if Review didn't block
        test_report = None
        if review_report["decision"] != "BLOCK":
            logger.info(f"[{request.pipeline_id}] Handing off to TestAgent...")
            test_report = await run_test_analysis(pipeline_data)
            logger.info(f"[TEST DONE] {request.pipeline_id} — decision={test_report['decision']}, coverage={test_report['scores']['coverage']}")
            await db.save_agent_decision(request.pipeline_id, "TestAgent", test_report)
        else:
            logger.info(f"[{request.pipeline_id}] Skipping TestAgent (Review blocked the pipeline)")

        # ============ Update Pipeline Status ============
        final_decision = review_report["decision"]
        if test_report and test_report["decision"] == "REQUEST_TESTS":
            final_decision = "REQUEST_CHANGES"

        await db.update_pipeline_status(
            request.pipeline_id,
            request.timestamp,
            {
                "status": "complete",
                "review_score": review_report["scores"]["overall"],
                "decision": final_decision,
                "total_findings": sum(review_report["summary"].values()),
                "coverage_score": test_report["scores"]["coverage"] if test_report else None,
            },
        )

        # ============ Post Combined Comment ============
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
