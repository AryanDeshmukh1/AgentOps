import crypto from 'crypto';
import logger from '../utils/logger.js';

/**
 * Verifies GitHub webhook HMAC signature.
 * GitHub signs every webhook with the secret you configured in the GitHub App.
 * If the signature doesn't match, the webhook is rejected as untrusted.
 */
export function verifyGitHubWebhook(req, res, next) {
  const signature = req.headers['x-hub-signature-256'];
  const secret = process.env.GITHUB_WEBHOOK_SECRET;

  if (!signature) {
    logger.warn('Webhook rejected: missing signature header');
    return res.status(401).json({ error: 'Missing signature' });
  }

  if (!secret) {
    logger.error('GITHUB_WEBHOOK_SECRET not configured');
    return res.status(500).json({ error: 'Server misconfiguration' });
  }

  // Compute the expected signature using HMAC-SHA256
  const hmac = crypto.createHmac('sha256', secret);
  const digest = 'sha256=' + hmac.update(req.rawBody).digest('hex');

  // Use timing-safe comparison to prevent timing attacks
  const signatureBuffer = Buffer.from(signature);
  const digestBuffer = Buffer.from(digest);

  if (signatureBuffer.length !== digestBuffer.length ||
      !crypto.timingSafeEqual(signatureBuffer, digestBuffer)) {
    logger.warn('Webhook rejected: invalid signature');
    return res.status(401).json({ error: 'Invalid signature' });
  }

  // Signature valid — proceed
  next();
}