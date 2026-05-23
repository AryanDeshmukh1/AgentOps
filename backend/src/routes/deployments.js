import express from "express";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  ScanCommand,
  UpdateCommand,
  GetCommand,
  PutCommand,
  QueryCommand,
} from "@aws-sdk/lib-dynamodb";
import logger from "../utils/logger.js";

const router = express.Router();
const client = new DynamoDBClient({ region: process.env.AWS_REGION || "ca-central-1" });
const docClient = DynamoDBDocumentClient.from(client);

const DEPLOYMENTS_TABLE = process.env.DYNAMODB_DEPLOYMENTS_TABLE || "AgentOps-Deployments";
const EVENTS_TABLE = process.env.DYNAMODB_DEPLOYMENT_EVENTS_TABLE || "AgentOps-DeploymentEvents";

// Deployment states (mirror agents/deploy_agent/deployment_state_machine.py)
const STATES = {
  PENDING: "pending",
  PROVISIONING: "provisioning",
  SMOKE_TEST: "smoke_test",
  READY_FOR_TRAFFIC_SHIFT: "ready_for_traffic_shift",
  TRAFFIC_SHIFTING: "traffic_shifting",
  MONITORING: "monitoring",
  PROMOTED: "promoted",
  ROLLED_BACK: "rolled_back",
  FAILED: "failed",
};

const TERMINAL_STATES = new Set([STATES.PROMOTED, STATES.ROLLED_BACK, STATES.FAILED]);
const ROLLBACK_ELIGIBLE = new Set([STATES.PROMOTED, STATES.MONITORING]);

/** List recent deployments. */
router.get("/", async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit) || 20, 100);
  try {
    const result = await docClient.send(new ScanCommand({
      TableName: DEPLOYMENTS_TABLE,
      Limit: limit,
    }));
    const items = result.Items || [];
    items.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    res.json({ count: items.length, deployments: items.slice(0, limit) });
  } catch (err) {
    logger.error(`Failed to list deployments: ${err.message}`);
    res.status(500).json({ error: err.message });
  }
});

/** Get one deployment. */
router.get("/:pipelineId/:deploymentId", async (req, res) => {
  const { pipelineId, deploymentId } = req.params;
  try {
    const result = await docClient.send(new GetCommand({
      TableName: DEPLOYMENTS_TABLE,
      Key: { pipeline_id: pipelineId, deployment_id: deploymentId },
    }));
    if (!result.Item) return res.status(404).json({ error: "Deployment not found" });
    res.json(result.Item);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/** Full audit trail for a deployment. */
router.get("/:pipelineId/:deploymentId/events", async (req, res) => {
  const { deploymentId } = req.params;
  try {
    const result = await docClient.send(new QueryCommand({
      TableName: EVENTS_TABLE,
      KeyConditionExpression: "deployment_id = :did",
      ExpressionAttributeValues: { ":did": deploymentId },
      ScanIndexForward: true,
    }));
    res.json({ deployment_id: deploymentId, events: result.Items || [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/**
 * Manual rollback — for an already-promoted (or monitoring) deployment.
 * Reverts traffic to 100% blue, transitions to rolled_back, writes audit event.
 *
 * POST /api/deployments/:pipelineId/:deploymentId/rollback
 * Body: { triggered_by: "alice", reason: "Customer reported broken checkout" }
 */
router.post("/:pipelineId/:deploymentId/rollback", async (req, res) => {
  const { pipelineId, deploymentId } = req.params;
  const { triggered_by = "anonymous", reason = "Manual rollback requested" } = req.body || {};

  // 1. Load current state
  const current = await docClient.send(new GetCommand({
    TableName: DEPLOYMENTS_TABLE,
    Key: { pipeline_id: pipelineId, deployment_id: deploymentId },
  }));
  if (!current.Item) {
    return res.status(404).json({ error: "Deployment not found" });
  }

  const currentStatus = current.Item.status;

  if (!ROLLBACK_ELIGIBLE.has(currentStatus)) {
    return res.status(400).json({
      error: `Cannot rollback deployment in state '${currentStatus}'. ` +
             `Only 'promoted' and 'monitoring' deployments can be manually rolled back.`,
    });
  }

  // 2. Revert traffic split
  try {
    await docClient.send(new UpdateCommand({
      TableName: DEPLOYMENTS_TABLE,
      Key: { pipeline_id: pipelineId, deployment_id: deploymentId },
      UpdateExpression: "SET traffic_split = :split, last_updated_at = :now",
      ExpressionAttributeValues: {
        ":split": { blue: 100, green: 0 },
        ":now": new Date().toISOString(),
      },
    }));
  } catch (err) {
    return res.status(500).json({ error: `Traffic revert failed: ${err.message}` });
  }

  // 3. Conditional state transition
  try {
    await docClient.send(new UpdateCommand({
      TableName: DEPLOYMENTS_TABLE,
      Key: { pipeline_id: pipelineId, deployment_id: deploymentId },
      UpdateExpression:
        "SET #status = :new, last_updated_at = :now, last_updated_by = :actor, last_comment = :comment",
      ConditionExpression: "#status = :expected",
      ExpressionAttributeNames: { "#status": "status" },
      ExpressionAttributeValues: {
        ":new": STATES.ROLLED_BACK,
        ":expected": currentStatus,
        ":actor": triggered_by,
        ":now": new Date().toISOString(),
        ":comment": `Manual rollback: ${reason}`,
      },
    }));
  } catch (err) {
    if (err.name === "ConditionalCheckFailedException") {
      return res.status(409).json({
        error: "Deployment state changed during rollback — please retry",
      });
    }
    return res.status(500).json({ error: err.message });
  }

  // 4. Audit event
  const event = {
    deployment_id: deploymentId,
    event_timestamp: new Date().toISOString(),
    from_state: currentStatus,
    to_state: STATES.ROLLED_BACK,
    actor: triggered_by,
    comment: `Manual rollback: ${reason}`,
    metadata: {
      manual: true,
      reason,
      traffic_reverted_to: { blue: 100, green: 0 },
    },
  };
  await docClient.send(new PutCommand({ TableName: EVENTS_TABLE, Item: event }));

  logger.info(`Manual rollback executed: ${deploymentId} by ${triggered_by}`);

  res.json({
    rolled_back: true,
    deployment_id: deploymentId,
    previous_state: currentStatus,
    new_state: STATES.ROLLED_BACK,
    traffic_split: { blue: 100, green: 0 },
    triggered_by,
    reason,
    event,
  });
});

export default router;