"""
AgentOps Agent System — FastAPI server hosting the multi-agent orchestrator.
"""
import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agentops")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle"""
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:4000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# Health Endpoints
# ============================================================

@app.get("/")
async def root():
    return {
        "name": "AgentOps Agent System",
        "version": "0.1.0",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "agentops-agents",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/health/deep")
async def health_deep():
    return {
        "status": "healthy",
        "service": "agentops-agents",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": {
            "api": "healthy",
            "gemini": "pending_integration",
            "dynamodb": "pending_integration",
            "sqs": "pending_integration",
        },
    }


# ============================================================
# Pipeline Models
# ============================================================

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


# ============================================================
# Pipeline Endpoints
# ============================================================

@app.post("/api/review")
async def receive_review_request(request: ReviewRequest):
    """
    Receives a PR for review and runs ReviewAgent.
    Currently runs Layer 1 (regex pattern scanning).
    """
    logger.info("=" * 60)
    logger.info(f"NEW PIPELINE: {request.pipeline_id}")
    logger.info(f"  Repo: {request.repo}")
    logger.info(f"  PR #{request.pr_number}: {request.pr_title}")
    logger.info(f"  Author: {request.pr_author}")
    logger.info(f"  Files changed: {len(request.files)}")
    logger.info("=" * 60)

    # Convert Pydantic model to dict for the agent
    pipeline_data = request.model_dump()

    # Import here to avoid circular imports
    from review_agent.agent import run_review

    try:
        report = await run_review(pipeline_data)

        # Log the report summary
        logger.info("=" * 60)
        logger.info(f"REVIEW COMPLETE: {request.pipeline_id}")
        logger.info(f"  Decision: {report['decision']}")
        logger.info(f"  Reason: {report['reason']}")
        logger.info(f"  Scores:")
        logger.info(f"    Overall:        {report['scores']['overall']}/100")
        logger.info(f"    Security:       {report['scores']['security']}/100")
        logger.info(f"    Code Quality:   {report['scores']['code_quality']}/100")
        logger.info(f"    Performance:    {report['scores']['performance']}/100")
        logger.info(f"    Architecture:   {report['scores']['architecture']}/100")
        logger.info(f"    Test Impact:    {report['scores']['test_impact']}/100")
        logger.info(f"    Documentation:  {report['scores']['documentation']}/100")
        logger.info(f"  Findings: {report['summary']}")

        if report['findings']:
            logger.info("  Top findings:")
            for f in report['findings'][:5]:  # Show top 5
                logger.info(f"    [{f['severity'].upper()}] {f['file']}:{f['line']} — {f['title']}")

        logger.info("=" * 60)

        return {
            "status": "completed",
            "pipeline_id": request.pipeline_id,
            "report": report,
        }
    except Exception as e:
        logger.error(f"[{request.pipeline_id}] Review failed: {e}", exc_info=True)
        return {
            "status": "error",
            "pipeline_id": request.pipeline_id,
            "error": str(e),
        }
   