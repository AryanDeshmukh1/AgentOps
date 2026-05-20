import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, ScanCommand, QueryCommand } from "@aws-sdk/lib-dynamodb";
import logger from "../utils/logger.js";

const client = new DynamoDBClient({
  region: process.env.AWS_REGION || "ca-central-1",
});
const docClient = DynamoDBDocumentClient.from(client);

const PIPELINES_TABLE = process.env.DYNAMODB_PIPELINES_TABLE || "AgentOps-Pipelines";
const DECISIONS_TABLE = process.env.DYNAMODB_AGENT_DECISIONS_TABLE || "AgentOps-AgentDecisions";

/**
 * Get recent pipelines, sorted by creation time (newest first).
 */
export async function listRecentPipelines(limit = 20) {
  try {
    const command = new ScanCommand({
      TableName: PIPELINES_TABLE,
      Limit: limit,
    });
    const result = await docClient.send(command);
    const items = result.Items || [];
    items.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    return items.slice(0, limit);
  } catch (err) {
    logger.error(`Failed to list pipelines: ${err.message}`);
    throw err;
  }
}

/**
 * Get all agent decisions for a specific pipeline.
 */
export async function getPipelineDecisions(pipelineId) {
  try {
    const command = new QueryCommand({
      TableName: DECISIONS_TABLE,
      KeyConditionExpression: "pipeline_id = :pid",
      ExpressionAttributeValues: { ":pid": pipelineId },
    });
    const result = await docClient.send(command);
    return result.Items || [];
  } catch (err) {
    logger.error(`Failed to get decisions for ${pipelineId}: ${err.message}`);
    throw err;
  }
}
