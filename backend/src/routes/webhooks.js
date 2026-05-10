import express from 'express';
import { verifyGitHubWebhook } from '../middleware/verifyGitHubWebhook.js';
import { getPullRequestFiles, setCommitStatus } from '../services/githubService.js';
import logger from '../utils/logger.js';

const router = express.Router();

/**
 * GitHub webhook receiver.
 * Receives PR events, validates signature, extracts data, forwards to agent service.
 */
router.post('/github', verifyGitHubWebhook, async (req, res) => {
  const event = req.headers['x-github-event'];
  const deliveryId = req.headers['x-github-delivery'];
  const action = req.body.action;

  logger.info(`Webhook received: event=${event}, action=${action}, delivery=${deliveryId}`);

  // Acknowledge GitHub immediately (must respond within 10 seconds)
  res.status(202).json({ received: true, deliveryId });

  // Process asynchronously — only handle pull_request events for now
  if (event !== 'pull_request') {
    logger.info(`Ignoring event type: ${event}`);
    return;
  }

  // Only process opened, synchronize (new commits), and reopened actions
  const relevantActions = ['opened', 'synchronize', 'reopened'];
  if (!relevantActions.includes(action)) {
    logger.info(`Ignoring PR action: ${action}`);
    return;
  }

  try {
    await processPullRequest(req.body);
  } catch (err) {
    logger.error(`Error processing PR webhook: ${err.message}`);
  }
});

/**
 * Process a pull request event end-to-end.
 */
async function processPullRequest(payload) {
  const pr = payload.pull_request;
  const repo = payload.repository;

  const owner = repo.owner.login;
  const repoName = repo.name;
  const prNumber = pr.number;
  const headSha = pr.head.sha;

  logger.info(`Processing PR #${prNumber} in ${owner}/${repoName}`);

  // Set initial status: "AgentOps Review Pending"
  try {
    await setCommitStatus(
      owner,
      repoName,
      headSha,
      'pending',
      'AgentOps review queued',
    );
  } catch (err) {
    logger.warn(`Could not set commit status: ${err.message}`);
  }

  // Fetch the changed files
  const files = await getPullRequestFiles(owner, repoName, prNumber);
  logger.info(`PR #${prNumber} has ${files.length} changed file(s)`);

  // Build the payload for the agent service
  const agentPayload = {
    pipeline_id: `pipe_${repoName}_${prNumber}_${Date.now()}`,
    repo: `${owner}/${repoName}`,
    pr_number: prNumber,
    pr_title: pr.title,
    pr_author: pr.user.login,
    pr_body: pr.body || '',
    head_sha: headSha,
    base_sha: pr.base.sha,
    files: files,
    timestamp: new Date().toISOString(),
  };

  // Forward to Python agent service
  await forwardToAgentService(agentPayload);
}

/**
 * Sends PR data to the Python agent service for analysis.
 */
async function forwardToAgentService(payload) {
  const agentsUrl = process.env.AGENTS_URL || 'http://agents:5000';

  try {
    const response = await fetch(`${agentsUrl}/api/review`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(`Agent service responded ${response.status}`);
    }

    const result = await response.json();
    logger.info(`Agent service accepted pipeline: ${payload.pipeline_id}`);
    return result;
  } catch (err) {
    logger.error(`Failed to forward to agent service: ${err.message}`);
    throw err;
  }
}

export default router;