"""
AgentOps Agent System — FastAPI server hosting the multi-agent orchestrator.
"""
import os
import logging
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    # TODO: Add real checks for DynamoDB, SQS, Gemini API as integrated
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
