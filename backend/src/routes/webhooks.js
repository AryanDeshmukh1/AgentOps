import express from 'express';
import { verifyGitHubWebhook } from '../middleware/verifyGitHubWebhook.js';
import { getPullRequestFiles, setCommitStatus, postPullRequestComment } from '../services/githubService.js';
import logger from '../utils/logger.js';

const router = express.Router();

router.post('/github', verifyGitHubWebhook, async (req, res) => {
  const event = req.headers['x-github-event'];
  const deliveryId = req.headers['x-github-delivery'];
  const action = req.body.action;

  logger.info(`Webhook received: event=${event}, action=${action}, delivery=${deliveryId}`);

  res.status(202).json({ received: true, deliveryId });

  if (event !== 'pull_request') {
    logger.info(`Ignoring event type: ${event}`);
    return;
  }

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

async function processPullRequest(payload) {
  const pr = payload.pull_request;
  const repo = payload.repository;
  const owner = repo.owner.login;
  const repoName = repo.name;
  const prNumber = pr.number;
  const headSha = pr.head.sha;

  logger.info(`Processing PR #${prNumber} in ${owner}/${repoName}`);

  try {
    await setCommitStatus(owner, repoName, headSha, 'pending', 'AgentOps review queued');
  } catch (err) {
    logger.warn(`Could not set commit status: ${err.message}`);
  }

  const files = await getPullRequestFiles(owner, repoName, prNumber);
  logger.info(`PR #${prNumber} has ${files.length} changed file(s)`);

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

  await forwardToAgentService(agentPayload);
}

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

router.post('/post-review', async (req, res) => {
  const { repo, pr_number, comment, head_sha, decision } = req.body;

  if (!repo || !pr_number || !comment) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  const [owner, repoName] = repo.split('/');

  try {
    await postPullRequestComment(owner, repoName, pr_number, comment);
    logger.info(`Posted review comment on ${repo}#${pr_number}`);

    if (head_sha && decision) {
      const statusMap = {
        'AUTO_APPROVE': 'success',
        'PASS_WITH_WARNINGS': 'success',
        'REQUEST_CHANGES': 'failure',
        'BLOCK': 'failure',
        'REJECT': 'failure',
      };
      const state = statusMap[decision] || 'pending';
      const description = `AgentOps: ${decision.replace(/_/g, ' ')}`;

      try {
        await setCommitStatus(owner, repoName, head_sha, state, description);
        logger.info(`Set commit status: ${state} on ${head_sha.substring(0, 8)}`);
      } catch (err) {
        logger.warn(`Could not set commit status: ${err.message}`);
      }
    }

    res.json({ posted: true });
  } catch (err) {
    logger.error(`Failed to post review comment: ${err.message}`);
    res.status(500).json({ error: err.message });
  }
});

export default router;
