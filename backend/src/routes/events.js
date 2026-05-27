import express from "express";
import { broadcast, CHANNELS, channelStats } from "../services/wsBroadcaster.js";
import logger from "../utils/logger.js";

const router = express.Router();

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

router.get("/stats", (req, res) => {
  res.json({
    channels: channelStats(),
    valid_channels: Object.values(CHANNELS),
  });
});

export default router;