# AgentOps — Setup & Configuration Log

**Project:** AgentOps — Multi-Agent DevOps Pipeline Orchestrator
**Author:** Aryan Deshmukh
**Started:** May 2026
**Status:** Day 1 — Environment Setup Complete

---

## Table of Contents

1. Project Overview
2. Development Environment
3. AWS Account Setup
4. AWS CLI Configuration
5. Gemini API Setup
6. Security Practices Established
7. Verification Tests Completed
8. Next Steps

---

## 1. Project Overview

AgentOps is a multi-agent AI system that autonomously manages CI/CD pipelines. The platform uses 4 specialized AI agents (ReviewAgent, TestAgent, DeployAgent, IncidentAgent) orchestrated by a LangGraph state machine, with human-in-the-loop governance for critical actions.

**Architecture goals:**
- Fully serverless cloud-native deployment on AWS free tier
- Zero infrastructure cost using AWS Lambda, DynamoDB, SQS
- AI reasoning via Google Gemini API free tier
- Real-time dashboard built with React, hosted on Vercel

---

## 2. Development Environment

### Operating System
- **Platform:** Windows
- **Shell:** PowerShell

### Tools Installed

| Tool | Purpose | Verification Command |
|------|---------|----------------------|
| Node.js (LTS) | Backend runtime, frontend build tools | `node --version` |
| Python 3.11+ | Agent system, ML/AI processing | `python --version` |
| Docker Desktop | Container orchestration for local dev | `docker --version` |
| Git | Version control | `git --version` |
| AWS CLI | AWS resource management | `aws --version` |

### Recommended Editor Setup
- Visual Studio Code with extensions: Python, ES7+ React/Redux/React-Native snippets, Tailwind CSS IntelliSense, Docker, AWS Toolkit

---

## 3. AWS Account Setup

### Account Creation
- AWS account created at https://aws.amazon.com/free
- Account type: Personal
- Support plan: Basic (Free)
- Default region selected: ca-central-1 (Canada Central — closest to Toronto for low latency)

### Budget Safety Net
- AWS Budget created with the following configuration:
  - Budget name: AgentOps-Safety
  - Budget type: Cost budget (Customize advanced)
  - Period: Monthly recurring
  - Budgeting method: Fixed
  - Budget amount: $1.00 USD
  - Alert thresholds: 80% and 100% of budgeted amount
  - Trigger: Actual spend
  - Notification: Email

**Purpose:** Prevents unexpected charges by sending email alerts the moment any AWS service starts accruing costs. Since the entire project runs on free tier, alerts should never trigger under normal operation.

---

## 4. AWS CLI Configuration

### IAM User Created
A dedicated IAM user was created for the project to follow AWS security best practices (root account is never used for daily operations).

- **Username:** agentops-dev
- **Console access:** Enabled
- **Programmatic access:** Enabled (CLI access keys generated)

### IAM Policies Attached
The following AWS managed policies were attached to grant the necessary permissions for AgentOps to function:

- AmazonDynamoDBFullAccess — for pipeline state storage and agent decision logs
- AmazonSQSFullAccess — for inter-agent message passing
- AmazonS3FullAccess — for deployment artifact storage
- AmazonSNSFullAccess — for alert notifications
- AmazonSESFullAccess — for incident report emails
- CloudWatchFullAccess — for post-deploy log monitoring and anomaly detection
- AWSLambda_FullAccess — for serverless agent execution
- AmazonAPIGatewayAdministrator — for REST and WebSocket API endpoints
- AmazonCognitoPowerUser — for dashboard authentication

### CLI Configuration
The AWS CLI was configured locally with the following parameters:

- AWS Access Key ID: [stored locally, never committed]
- AWS Secret Access Key: [stored locally, never committed]
- Default region: ca-central-1
- Default output format: json

### Authentication Verification
The AWS CLI authentication was verified successfully using:

```bash
aws sts get-caller-identity
```

Confirmed the configured user (agentops-dev) is authenticated and able to communicate with AWS services in the ca-central-1 region.

---

## 5. Gemini API Setup

### API Key Generation
- Account: Google AI Studio (https://aistudio.google.com)
- API Key created via the Get API Key flow
- Free tier limits confirmed:
  - Gemini 2.5 Flash: 10 requests per minute, 250 daily requests
  - Gemini 2.5 Flash-Lite: 15 requests per minute, 1,000 daily requests
- No credit card required for free tier access

### Connection Verification
A test API call was made to verify the API key is functional and the model responds correctly. The Gemini 2.5 Flash model successfully returned a structured JSON response, confirming:

- API key is valid and authenticated
- Network connectivity to Google AI services is working
- Response parsing pipeline can be built on this foundation

---

## 6. Security Practices Established

### Secrets Management Policy
The following security practices have been adopted for the project:

- **API keys never go in source code:** All secrets will be stored in `.env` files
- **`.env` files added to `.gitignore`:** Never committed to GitHub
- **Initial Gemini API key compromised and rotated:** During setup, the original API key was accidentally shared and immediately revoked. A new key was generated to replace it. This established the discipline of treating credentials as sensitive at all times.
- **AWS Account ID treated as semi-sensitive:** Will be masked in shared logs and screenshots
- **IAM user used for daily work:** Root account credentials are stored securely and not used for routine operations
- **Credentials rotation plan:** API keys and access keys will be rotated if any potential compromise occurs

### Cost Protection
- $1 monthly budget alert active on AWS account
- All resources will be created on free tier services only
- EC2 instances (if any) will be stopped when not actively in use
- Periodic billing dashboard reviews scheduled

---

## 7. Verification Tests Completed

| Test | Command | Result |
|------|---------|--------|
| Node.js installed | `node --version` | Pass |
| Python installed | `python --version` | Pass |
| Docker installed | `docker --version` | Pass |
| Git installed | `git --version` | Pass |
| AWS CLI installed | `aws --version` | Pass |
| AWS authentication working | `aws sts get-caller-identity` | Pass — user agentops-dev authenticated |
| Gemini API responding | curl test to gemini-2.5-flash endpoint | Pass — received valid JSON response |

---

## 8. Next Steps

The development environment is now fully prepared. The following tasks remain for Day 1 completion:

### AWS Resource Provisioning
- Create 6 DynamoDB tables (Pipelines, AgentDecisions, Approvals, Incidents, Metrics, DeployLocks)
- Create 6 SQS queues (DeadLetter, Review, Test, Approval, Deploy, Incident)
- Create 1 S3 bucket for deployment artifacts

### Project Scaffolding
- Initialize monorepo structure (frontend, backend, agents folders)
- Set up Docker Compose for local development orchestration
- Initialize Git repository with appropriate `.gitignore`
- Create `.env.example` template (committed) and `.env` file (not committed)
- Set up basic health endpoints in backend
- Initialize React app shell with Vite and Tailwind CSS

### Day 1 Deliverable
By the end of Day 1, all AWS infrastructure should be provisioned and the local development environment should be running with `docker compose up`.

---

## Lessons Learned (Day 1)

- **Credential hygiene matters from minute one:** Even during setup, API keys can be accidentally exposed. Establishing a strict no-secrets-in-chat-or-code policy from the start prevents real production incidents later.
- **Region choice impacts latency:** Selecting ca-central-1 over us-east-1 ensures the lowest possible latency for development from Toronto, which matters when testing real-time WebSocket features.
- **Budget alerts are non-negotiable:** Even on free tier, services like data transfer can have unexpected costs. The $1 budget alert provides peace of mind and acts as an early warning system.
- **Use IAM users, not root:** Following AWS Well-Architected security best practices from day one establishes professional habits that translate directly to enterprise environments.

---

*This document will be updated daily as the project progresses through its 35-day build timeline.*
