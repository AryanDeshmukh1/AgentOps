

# AgentOps — Multi-Agent DevOps Pipeline Orchestrator

> An autonomous multi-agent AI system that manages CI/CD pipelines from code review through deployment to incident response, with human-in-the-loop governance.

🌐 Live Demo
The dashboard is deployed and live:
👉 https://jovial-sherbet-47a417.netlify.app
The backend services run on Render's free tier and spin down after 15 min of inactivity, so the first load may take 30-60 seconds while the backend wakes up. Once warm, real-time updates work immediately.
What you can try on the live demo:

Browse real pipelines that flowed through all 4 agents (12+ pipelines with actual Gemini findings)
Click into a pipeline to see the agent timeline, score breakdown radar chart, and findings list
View blue/green deployments with animated traffic visualization
Open the incidents page to see anomaly detection + AI-generated root cause analysis
Press Cmd+K to open the command palette
Try the guided tour (button in the bottom-right corner)

## Overview

AgentOps uses 4 specialized AI agents orchestrated by a LangGraph state machine:

- **ReviewAgent** — 6-layer code analysis (OWASP security, code quality, performance, architecture, test impact, documentation)
- **TestAgent** — Automated test generation and execution with coverage analysis
- **DeployAgent** — Blue/green deployment with canary traffic shifting and auto-rollback
- **IncidentAgent** — Post-deployment monitoring with Z-score anomaly detection and AI-powered root cause correlation

## Architecture

```
GitHub PR → ReviewAgent → TestAgent → Human Approval → DeployAgent → IncidentAgent
```

All agents communicate via AWS SQS, persist state in DynamoDB, and execute as serverless Lambda functions.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite + Tailwind CSS + Recharts |
| Backend API | Node.js + Express + Socket.io |
| Agent System | Python + LangGraph + Gemini API |
| Infrastructure | AWS (Lambda, API Gateway, DynamoDB, SQS, S3, CloudWatch, Cognito) |
| Containerization | Docker + Docker Compose |
| CI/CD | GitHub Actions |

## Prerequisites

- Node.js 22.x LTS
- Python 3.11+
- Docker Desktop
- AWS CLI (configured)
- Gemini API key

## Quick Start

```bash
# Clone and enter project
cd C:\AgentOps

# Copy environment template and fill in your values
cp .env.example .env

# Start all services
docker compose up

# Frontend: http://localhost:3000
# Backend:  http://localhost:4000
# Agents:   http://localhost:5000
```

## Project Structure

```
AgentOps/
├── backend/          Node.js Express API + WebSocket server
├── frontend/         React dashboard
├── agents/           Python multi-agent system (LangGraph)
├── scripts/          Setup and utility scripts
├── docs/             Architecture diagrams and documentation
├── docker-compose.yml
├── .env.example
└── README.md


