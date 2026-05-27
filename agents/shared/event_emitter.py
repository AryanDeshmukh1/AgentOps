"""
EventEmitter — fire-and-forget event emission from agents to the backend.

Backend rebroadcasts to subscribed WebSocket clients via /api/events/agent.

Design principles:
  - Never block the agent's state machine
  - Never raise an exception that could fail the agent
  - Timeout aggressively (3s); a slow backend should NOT slow the agent
  - Log failures so we can diagnose, but always swallow errors
"""
import os
from typing import Dict, Any, Optional
import httpx

from shared.logger import get_logger

logger = get_logger(__name__)


# Channel taxonomy (mirrors backend/src/services/wsBroadcaster.js)
class Channels:
    PIPELINES = "pipelines"
    APPROVALS = "approvals"
    DEPLOYMENTS = "deployments"
    INCIDENTS = "incidents"


async def emit_event(
    channel: str,
    type: str,
    payload: Optional[Dict[str, Any]] = None,
    source: str = "agent",
) -> bool:
    """
    Fire an event to the backend, which rebroadcasts via WebSocket.

    Returns True on success, False on any failure. Never raises.
    """
    backend_url = os.getenv("BACKEND_URL", "http://backend:4000")
    body = {
        "channel": channel,
        "type": type,
        "payload": payload or {},
        "source": source,
    }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                f"{backend_url}/api/events/agent",
                json=body,
            )
            if response.status_code == 200:
                logger.debug(f"[EventEmitter] {channel}.{type} emitted")
                return True
            logger.warning(
                f"[EventEmitter] {channel}.{type} returned HTTP {response.status_code}"
            )
            return False
    except Exception as e:
        # Never raise — agent flow must not depend on backend availability
        logger.warning(f"[EventEmitter] {channel}.{type} failed: {type(e).__name__}: {e}")
        return False