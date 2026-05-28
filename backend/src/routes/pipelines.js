import express from "express";
import {
  listRecentPipelines,
  getPipelineDecisions,
  listPipelinesPaginated,
} from "../services/dynamodbService.js";
import {
  parsePaginationParams,
  buildPaginatedResponse,
} from "../utils/pagination.js";
import logger from "../utils/logger.js";

const router = express.Router();

/**
 * GET /api/pipelines
 *
 * Query params:
 *   limit       — page size (1-100, default 20)
 *   cursor      — base64-encoded continuation token
 *   status      — filter: running | complete | blocked | awaiting_approval | failed
 *   repo        — filter: exact repo name (e.g., "owner/name")
 *   risk_level  — filter: auto | soft | hard
 *
 * Response:
 *   { items: [...], count: N, next_cursor: "..." | null }
 */
router.get("/", async (req, res, next) => {
  try {
    const { limit, exclusiveStartKey } = parsePaginationParams(req);
    const result = await listPipelinesPaginated({
      limit,
      exclusiveStartKey,
      status: req.query.status,
      repo: req.query.repo,
      riskLevel: req.query.risk_level,
    });
    res.json(buildPaginatedResponse(result));
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/pipelines/:id/decisions
 * Returns all agent decisions for a pipeline.
 */
router.get("/:id/decisions", async (req, res, next) => {
  const pipelineId = req.params.id;
  try {
    const decisions = await getPipelineDecisions(pipelineId);
    res.json({ pipeline_id: pipelineId, count: decisions.length, decisions });
  } catch (err) {
    next(err);
  }
});

export default router;