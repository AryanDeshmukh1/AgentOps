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

/**
 * Paginated, filterable pipeline list.
 *
 * Filters supported: status, repo, risk_level
 * Pagination: cursor-based (LastEvaluatedKey)
 */
export async function listPipelinesPaginated({
  limit = 20,
  exclusiveStartKey = null,
  status = null,
  repo = null,
  riskLevel = null,
} = {}) {
  try {
    const filterParts = [];
    const exprValues = {};
    const exprNames = {};

    if (status) {
      filterParts.push("#status = :status");
      exprNames["#status"] = "status";
      exprValues[":status"] = status;
    }
    if (repo) {
      filterParts.push("repo = :repo");
      exprValues[":repo"] = repo;
    }
    if (riskLevel) {
      filterParts.push("risk_level = :rl");
      exprValues[":rl"] = riskLevel;
    }

    const scanParams = {
      TableName: PIPELINES_TABLE,
      Limit: limit,
    };
    if (filterParts.length > 0) {
      scanParams.FilterExpression = filterParts.join(" AND ");
      scanParams.ExpressionAttributeValues = exprValues;
      if (Object.keys(exprNames).length > 0) {
        scanParams.ExpressionAttributeNames = exprNames;
      }
    }
    if (exclusiveStartKey) {
      scanParams.ExclusiveStartKey = exclusiveStartKey;
    }

    const command = new ScanCommand(scanParams);
    const result = await docClient.send(command);

    // Sort the page newest-first (within the page)
    const items = result.Items || [];
    items.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));

    return {
      Items: items,
      LastEvaluatedKey: result.LastEvaluatedKey,
    };
  } catch (err) {
    logger.error(`Failed to list pipelines paginated: ${err.message}`);
    throw err;
  }
}