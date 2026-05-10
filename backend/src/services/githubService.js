import { Octokit } from '@octokit/rest';
import { createAppAuth } from '@octokit/auth-app';
import fs from 'fs';
import logger from '../utils/logger.js';

let octokitInstance = null;

/**
 * Returns an authenticated Octokit instance.
 * Uses GitHub App authentication with installation token.
 */
function getOctokit() {
  if (octokitInstance) return octokitInstance;

  const appId = process.env.GITHUB_APP_ID;
  const installationId = process.env.GITHUB_INSTALLATION_ID;
  const privateKeyPath = process.env.GITHUB_APP_PRIVATE_KEY_PATH;

  if (!appId || !installationId || !privateKeyPath) {
    throw new Error('GitHub App credentials not configured in .env');
  }

  const privateKey = fs.readFileSync(privateKeyPath, 'utf8');

  octokitInstance = new Octokit({
    authStrategy: createAppAuth,
    auth: {
      appId,
      privateKey,
      installationId,
    },
  });

  logger.info('GitHub Octokit client initialized');
  return octokitInstance;
}

/**
 * Fetches the diff and changed files for a pull request.
 */
export async function getPullRequestFiles(owner, repo, pullNumber) {
  const octokit = getOctokit();

  const { data: files } = await octokit.pulls.listFiles({
    owner,
    repo,
    pull_number: pullNumber,
  });

  return files.map(file => ({
    filename: file.filename,
    status: file.status,
    additions: file.additions,
    deletions: file.deletions,
    changes: file.changes,
    patch: file.patch || '',
  }));
}

/**
 * Posts a comment on a pull request.
 */
export async function postPullRequestComment(owner, repo, pullNumber, body) {
  const octokit = getOctokit();
  return octokit.issues.createComment({
    owner,
    repo,
    issue_number: pullNumber,
    body,
  });
}

/**
 * Sets a commit status (the green checkmark / yellow circle / red X).
 */
export async function setCommitStatus(owner, repo, sha, state, description, context = 'AgentOps/review') {
  const octokit = getOctokit();
  return octokit.repos.createCommitStatus({
    owner,
    repo,
    sha,
    state, // 'pending' | 'success' | 'failure' | 'error'
    description,
    context,
  });
}