/**
 * Cursor-based pagination for DynamoDB list endpoints.
 *
 * Frontend usage:
 *   GET /api/pipelines?limit=20            → first page
 *   GET /api/pipelines?cursor=eyJ...&limit=20  → next page
 *
 * Response shape: { items, count, next_cursor }
 */

const MAX_LIMIT = 100;
const DEFAULT_LIMIT = 20;

/** Parse query params into safe pagination args. */
export function parsePaginationParams(req) {
  let limit = parseInt(req.query.limit, 10) || DEFAULT_LIMIT;
  if (limit < 1) limit = DEFAULT_LIMIT;
  if (limit > MAX_LIMIT) limit = MAX_LIMIT;

  let exclusiveStartKey = null;
  if (req.query.cursor) {
    try {
      const decoded = Buffer.from(req.query.cursor, "base64").toString("utf-8");
      exclusiveStartKey = JSON.parse(decoded);
    } catch (e) {
      throw Object.assign(
        new Error("Invalid cursor"),
        { status: 400, code: "INVALID_CURSOR" }
      );
    }
  }

  return { limit, exclusiveStartKey };
}

/** Encode a DynamoDB LastEvaluatedKey for the client. */
export function encodeCursor(lastEvaluatedKey) {
  if (!lastEvaluatedKey) return null;
  return Buffer.from(JSON.stringify(lastEvaluatedKey)).toString("base64");
}

/** Build a paginated response from a Dynamo result. */
export function buildPaginatedResponse(result, items = null) {
  const data = items || result.Items || [];
  return {
    items: data,
    count: data.length,
    next_cursor: encodeCursor(result.LastEvaluatedKey),
  };
}