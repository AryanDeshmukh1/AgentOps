import rateLimit from "express-rate-limit";

/**
 * Strict limiter for public-facing endpoints that we don't trust callers on.
 * 60 requests per minute per IP.
 */
export const publicLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 60,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: "Too many requests, please slow down",
    code: "RATE_LIMITED",
  },
});

/**
 * Looser limiter for read-only endpoints (dashboard polling, list endpoints).
 * 300 requests per minute per IP.
 */
export const readLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 300,
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    error: "Too many requests, please slow down",
    code: "RATE_LIMITED",
  },
});