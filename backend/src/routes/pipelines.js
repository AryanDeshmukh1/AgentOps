import express from "express";
import { listRecentPipelines, getPipelineDecisions } from "../services/dynamodbService.js";
import logger from "../utils/logger.js";

const router = express.Router();

/**
 * GET /api/pipelines
 * Returns recent pipeline records.
 */
router.get("/", async (req, res) => {
  const limit = parseInt(req.query.limit) || 20;
  try {
    const pipelines = await listRecentPipelines(limit);
    res.json({ count: pipelines.length, pipelines });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /api/pipelines/:id/decisions
 * Returns all agent decisions for a pipeline.
 */
router.get("/:id/decisions", async (req, res) => {
  const pipelineId = req.params.id;
  try {
    const decisions = await getPipelineDecisions(pipelineId);
    res.json({ pipeline_id: pipelineId, count: decisions.length, decisions });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
