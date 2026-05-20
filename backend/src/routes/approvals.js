import express from "express";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, ScanCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import logger from "../utils/logger.js";

const router = express.Router();
const client = new DynamoDBClient({ region: process.env.AWS_REGION || "ca-central-1" });
const docClient = DynamoDBDocumentClient.from(client);
const APPROVALS_TABLE = process.env.DYNAMODB_APPROVALS_TABLE || "AgentOps-Approvals";

router.get("/pending", async (req, res) => {
  try {
    const command = new ScanCommand({
      TableName: APPROVALS_TABLE,
      FilterExpression: "#status = :pending",
      ExpressionAttributeNames: { "#status": "status" },
      ExpressionAttributeValues: { ":pending": "pending" },
    });
    const result = await docClient.send(command);
    const items = result.Items || [];
    items.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    res.json({ count: items.length, pending: items });
  } catch (err) {
    logger.error(`Failed to list pending approvals: ${err.message}`);
    res.status(500).json({ error: err.message });
  }
});

router.post("/:pipelineId/:approvalId/approve", async (req, res) => {
  const { pipelineId, approvalId } = req.params;
  const { approved_by = "anonymous", comment = "" } = req.body || {};
  try {
    await docClient.send(new UpdateCommand({
      TableName: APPROVALS_TABLE,
      Key: { pipeline_id: pipelineId, approval_id: approvalId },
      UpdateExpression: "SET #status = :s, approved_by = :u, approved_at = :t, #cmt = :c",
      ExpressionAttributeNames: { "#status": "status", "#cmt": "comment" },
      ExpressionAttributeValues: {
        ":s": "approved",
        ":u": approved_by,
        ":t": new Date().toISOString(),
        ":c": comment,
      },
    }));
    res.json({ status: "approved", pipeline_id: pipelineId, approval_id: approvalId });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.post("/:pipelineId/:approvalId/reject", async (req, res) => {
  const { pipelineId, approvalId } = req.params;
  const { rejected_by = "anonymous", comment = "" } = req.body || {};
  try {
    await docClient.send(new UpdateCommand({
      TableName: APPROVALS_TABLE,
      Key: { pipeline_id: pipelineId, approval_id: approvalId },
      UpdateExpression: "SET #status = :s, approved_by = :u, approved_at = :t, #cmt = :c",
      ExpressionAttributeNames: { "#status": "status", "#cmt": "comment" },
      ExpressionAttributeValues: {
        ":s": "rejected",
        ":u": rejected_by,
        ":t": new Date().toISOString(),
        ":c": comment,
      },
    }));
    res.json({ status: "rejected", pipeline_id: pipelineId, approval_id: approvalId });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
