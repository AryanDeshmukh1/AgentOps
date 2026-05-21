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
import { STATES, validateTransition, buildEvent } from "../services/approvalStateMachine.js";

const router = express.Router();
const client = new DynamoDBClient({ region: process.env.AWS_REGION || "ca-central-1" });
const docClient = DynamoDBDocumentClient.from(client);

const APPROVALS_TABLE = process.env.DYNAMODB_APPROVALS_TABLE || "AgentOps-Approvals";
const EVENTS_TABLE = process.env.DYNAMODB_APPROVAL_EVENTS_TABLE || "AgentOps-ApprovalEvents";

/** Atomic state transition: conditional update + audit event. */
async function transitionApproval({
  pipelineId,
  approvalId,
  newStatus,
  actor,
  comment,
  expectedStatus = STATES.PENDING,
}) {
  try {
    await docClient.send(new UpdateCommand({
      TableName: APPROVALS_TABLE,
      Key: { pipeline_id: pipelineId, approval_id: approvalId },
      UpdateExpression:
        "SET #status = :new, approved_by = :actor, approved_at = :now, #cmt = :comment",
      ConditionExpression: "#status = :expected",
      ExpressionAttributeNames: { "#status": "status", "#cmt": "comment" },
      ExpressionAttributeValues: {
        ":new": newStatus,
        ":expected": expectedStatus,
        ":actor": actor,
        ":now": new Date().toISOString(),
        ":comment": comment,
      },
    }));
  } catch (err) {
    if (err.name === "ConditionalCheckFailedException") {
      return { ok: false, code: 409, error: "Approval already decided or state changed" };
    }
    throw err;
  }

  const event = buildEvent(approvalId, expectedStatus, newStatus, actor, comment);
  await docClient.send(new PutCommand({ TableName: EVENTS_TABLE, Item: event }));

  return { ok: true, event };
}

router.get("/pending", async (req, res) => {
  try {
    const result = await docClient.send(new ScanCommand({
      TableName: APPROVALS_TABLE,
      FilterExpression: "#status = :pending",
      ExpressionAttributeNames: { "#status": "status" },
      ExpressionAttributeValues: { ":pending": STATES.PENDING },
    }));
    const items = result.Items || [];
    items.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    res.json({ count: items.length, pending: items });
  } catch (err) {
    logger.error(`Failed to list pending approvals: ${err.message}`);
    res.status(500).json({ error: err.message });
  }
});

router.get("/:pipelineId/:approvalId", async (req, res) => {
  const { pipelineId, approvalId } = req.params;
  try {
    const result = await docClient.send(new GetCommand({
      TableName: APPROVALS_TABLE,
      Key: { pipeline_id: pipelineId, approval_id: approvalId },
    }));
    if (!result.Item) return res.status(404).json({ error: "Approval not found" });
    res.json(result.Item);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.get("/:pipelineId/:approvalId/events", async (req, res) => {
  const { approvalId } = req.params;
  try {
    const result = await docClient.send(new QueryCommand({
      TableName: EVENTS_TABLE,
      KeyConditionExpression: "approval_id = :aid",
      ExpressionAttributeValues: { ":aid": approvalId },
      ScanIndexForward: true,
    }));
    res.json({ approval_id: approvalId, events: result.Items || [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.post("/:pipelineId/:approvalId/approve", async (req, res) => {
  const { pipelineId, approvalId } = req.params;
  const { approved_by = "anonymous", comment = "" } = req.body || {};

  const current = await docClient.send(new GetCommand({
    TableName: APPROVALS_TABLE,
    Key: { pipeline_id: pipelineId, approval_id: approvalId },
  }));
  if (!current.Item) return res.status(404).json({ error: "Approval not found" });

  const check = validateTransition(current.Item.status, STATES.APPROVED);
  if (!check.ok) return res.status(400).json({ error: check.error });

  try {
    const result = await transitionApproval({
      pipelineId, approvalId,
      newStatus: STATES.APPROVED,
      actor: approved_by,
      comment,
    });
    if (!result.ok) return res.status(result.code).json({ error: result.error });
    res.json({ status: STATES.APPROVED, pipeline_id: pipelineId, approval_id: approvalId, event: result.event });
  } catch (err) {
    logger.error(`Approve failed: ${err.message}`);
    res.status(500).json({ error: err.message });
  }
});

router.post("/:pipelineId/:approvalId/reject", async (req, res) => {
  const { pipelineId, approvalId } = req.params;
  const { rejected_by = "anonymous", comment = "" } = req.body || {};

  const current = await docClient.send(new GetCommand({
    TableName: APPROVALS_TABLE,
    Key: { pipeline_id: pipelineId, approval_id: approvalId },
  }));
  if (!current.Item) return res.status(404).json({ error: "Approval not found" });

  const check = validateTransition(current.Item.status, STATES.REJECTED);
  if (!check.ok) return res.status(400).json({ error: check.error });

  try {
    const result = await transitionApproval({
      pipelineId, approvalId,
      newStatus: STATES.REJECTED,
      actor: rejected_by,
      comment,
    });
    if (!result.ok) return res.status(result.code).json({ error: result.error });
    res.json({ status: STATES.REJECTED, pipeline_id: pipelineId, approval_id: approvalId, event: result.event });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;