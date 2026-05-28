import express from "express";
import { ScanCommand, QueryCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { docClient } from "../services/dynamodbService.js";
import logger from "../utils/logger.js";

const router = express.Router();

const INCIDENTS_TABLE = "AgentOps-Incidents";
const METRICS_TABLE = "AgentOps-Metrics";

/**
 * GET /api/incidents
 * Returns recent incidents across all deployments, newest first.
 *
 * Query params:
 *   limit  — page size (1-100, default 50)
 *   status — filter by status (open | acknowledged | resolved)
 */
router.get("/", async (req, res, next) => {
  try {
    const limit = Math.min(parseInt(req.query.limit, 10) || 50, 100);
    const statusFilter = req.query.status;

    const params = { TableName: INCIDENTS_TABLE };
    if (statusFilter) {
      params.FilterExpression = "#s = :s";
      params.ExpressionAttributeNames = { "#s": "status" };
      params.ExpressionAttributeValues = { ":s": statusFilter };
    }

    const result = await docClient.send(new ScanCommand(params));
    const items = result.Items || [];
    items.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));

    res.json({
      count: Math.min(items.length, limit),
      total: items.length,
      incidents: items.slice(0, limit),
    });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/incidents/:deploymentId/:incidentId
 * Returns the incident + a window of metrics surrounding the anomaly time
 * (default: 20 minutes before, 5 minutes after).
 */
router.get("/:deploymentId/:incidentId", async (req, res, next) => {
  try {
    const { deploymentId, incidentId } = req.params;

    const incidentResult = await docClient.send(new QueryCommand({
      TableName: INCIDENTS_TABLE,
      KeyConditionExpression: "deployment_id = :d AND incident_id = :i",
      ExpressionAttributeValues: { ":d": deploymentId, ":i": incidentId },
      Limit: 1,
    }));

    const incident = (incidentResult.Items || [])[0];
    if (!incident) {
      return res.status(404).json({
        error: "Incident not found",
        code: "NOT_FOUND",
        request_id: req.requestId,
      });
    }

    // Pull metrics for ~25 minutes around the incident fire time
    const firedAt = new Date(incident.created_at);
    const windowStart = new Date(firedAt.getTime() - 20 * 60 * 1000).toISOString();
    const windowEnd = new Date(firedAt.getTime() + 5 * 60 * 1000).toISOString();

    let metrics = [];
    try {
      const metricsResult = await docClient.send(new QueryCommand({
        TableName: METRICS_TABLE,
        KeyConditionExpression: "deployment_id = :d AND metric_timestamp BETWEEN :s AND :e",
        ExpressionAttributeValues: {
          ":d": deploymentId,
          ":s": windowStart,
          ":e": windowEnd,
        },
      }));
      metrics = metricsResult.Items || [];
      metrics.sort((a, b) => (a.metric_timestamp || "").localeCompare(b.metric_timestamp || ""));
    } catch (e) {
      logger.warn(`Could not load metrics for ${incidentId}: ${e.message}`);
    }

    res.json({ incident, metrics });
  } catch (err) {
    next(err);
  }
});

/**
 * POST /api/incidents/:deploymentId/:incidentId/acknowledge
 * POST /api/incidents/:deploymentId/:incidentId/resolve
 */
function makeTransitionHandler(targetStatus, actorField, timestampField) {
  return async (req, res, next) => {
    try {
      const { deploymentId, incidentId } = req.params;
      const actor = req.body?.actor || "anonymous";
      const comment = req.body?.comment || "";

      const result = await docClient.send(new UpdateCommand({
        TableName: INCIDENTS_TABLE,
        Key: { deployment_id: deploymentId, incident_id: incidentId },
        UpdateExpression: `SET #s = :status, ${actorField} = :actor, ${timestampField} = :ts, last_comment = :comment`,
        ExpressionAttributeNames: { "#s": "status" },
        ExpressionAttributeValues: {
          ":status": targetStatus,
          ":actor": actor,
          ":ts": new Date().toISOString(),
          ":comment": comment,
        },
        ReturnValues: "ALL_NEW",
      }));

      res.json({ incident: result.Attributes });
    } catch (err) {
      next(err);
    }
  };
}

router.post("/:deploymentId/:incidentId/acknowledge",
  makeTransitionHandler("acknowledged", "acknowledged_by", "acknowledged_at"));

router.post("/:deploymentId/:incidentId/resolve",
  makeTransitionHandler("resolved", "resolved_by", "resolved_at"));

export default router;