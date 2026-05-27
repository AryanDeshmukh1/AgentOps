import express from "express";
import { broadcast, CHANNELS, channelStats } from "../services/wsBroadcaster.js";
import logger from "../utils/logger.js";

const router = express.Router();
const VALID_CHANNELS = new Set(Object.values(CHANNELS));

/**
 * Manual emit — for testing the WS layer (Day 20).
 */
router.post("/emit", (req, res) => {
  const { channel, type, payload, source } = req.body || {};
  if (!channel || !type) {
    return res.status(400).json({ error: "channel and type are required" });
  }
  const ok = broadcast({
    channel,
    type,
    payload: payload || {},
    source: source || "manual",
  });
  if (!ok) {
    return res.status(400).json({ error: "Invalid channel or broadcaster not ready" });
  }
  res.json({ broadcast: true, channel, type });
});

/**
 * Agent event endpoint — receives events from Python agents and rebroadcasts via WS.
 *
 * POST /api/events/agent
 * { channel, type, payload, source }
 *
 * Returns quickly (fire-and-forget pattern); failures are logged but don't fail the agent.
 */
router.post("/agent", (req, res) => {
  const { channel, type, payload, source } = req.body || {};

  if (!channel || !VALID_CHANNELS.has(channel)) {
    logger.warn(`[/api/events/agent] Invalid channel: ${channel}`);
    return res.status(400).json({ error: `Unknown channel: ${channel}` });
  }
  if (!type) {
    return res.status(400).json({ error: "type is required" });
  }

  const ok = broadcast({
    channel,
    type,
    payload: payload || {},
    source: source || "agent",
  });

  if (!ok) {
    return res.status(500).json({ error: "Broadcast failed" });
  }

  res.json({ received: true });
});

/** Channel subscriber stats. */
router.get("/stats", (req, res) => {
  res.json({
    channels: channelStats(),
    valid_channels: Object.values(CHANNELS),
  });
});

export default router;