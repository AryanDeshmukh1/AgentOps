import { v4 as uuidv4 } from "uuid";
import logger from "../utils/logger.js";

/**
 * Attaches a request_id to every request — used in error responses for traceability.
 */
export function requestIdMiddleware(req, res, next) {
  req.requestId = req.headers["x-request-id"] || uuidv4();
  res.setHeader("X-Request-Id", req.requestId);
  next();
}

/**
 * Consistent error responses: { error, code, request_id }
 */
export function errorHandler(err, req, res, next) {
  const status = err.status || 500;
  const code = err.code || (status === 500 ? "INTERNAL_ERROR" : "ERROR");
  const message = err.message || "Internal Server Error";

  logger.error(
    `[${req.requestId}] ${req.method} ${req.path} → ${status} ${code}: ${message}`
  );

  res.status(status).json({
    error: message,
    code,
    request_id: req.requestId,
  });
}

/**
 * 404 handler — also uses the consistent shape.
 */
export function notFoundHandler(req, res) {
  res.status(404).json({
    error: "Not Found",
    code: "NOT_FOUND",
    request_id: req.requestId,
    path: req.path,
  });
}