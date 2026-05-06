# Day 1 — Project Scaffold Complete

**Date:** May 6, 2026
**Hours Logged:** 6h
**Status:** ✅ Day 1 complete

---

## What Was Built Today

### 1. Development Environment (✅)
- Installed: Node.js 22, Python 3.12, Docker Desktop, Git, AWS CLI
- All tools verified with `--version` commands

### 2. AWS Infrastructure (✅)
Provisioned in `ca-central-1` region:

**DynamoDB Tables (6):**
- `AgentOps-Pipelines` — pipeline state and metadata
- `AgentOps-AgentDecisions` — every decision made by every agent
- `AgentOps-Approvals` — human approval queue and history
- `AgentOps-Incidents` — incident detection and resolution
- `AgentOps-Metrics` — aggregated metrics for dashboard
- `AgentOps-DeployLocks` — concurrent deployment lock mechanism

**SQS Queues (6):**
- `AgentOps-DeadLetter` — failed messages for debugging
- `AgentOps-ReviewQueue` — webhook → ReviewAgent
- `AgentOps-TestQueue` — ReviewAgent → TestAgent
- `AgentOps-ApprovalQueue` — TestAgent → ApprovalGate
- `AgentOps-DeployQueue` — Approval → DeployAgent
- `AgentOps-IncidentQueue` — DeployAgent → IncidentAgent

**S3 Bucket:**
- `agentops-artifacts-aryan2026` — deployment artifact storage

### 3. Security Setup (✅)
- IAM user `agentops-dev` created with scoped permissions
- $1 monthly budget alert configured
- AWS CLI configured with least-privilege user (not root)
- Gemini API key obtained and rotated after accidental exposure (good lesson learned)

### 4. Project Scaffold (✅)
Created the complete monorepo structure at `C:\AgentOps`:

```
AgentOps/
├── backend/              Node.js + Express + Socket.io
│   ├── src/
│   │   ├── routes/       REST API endpoints
│   │   ├── services/     Business logic
│   │   ├── middleware/   Auth, validation, rate limiting
│   │   ├── utils/        Logger, helpers
│   │   └── server.js     Main entry
│   ├── package.json
│   └── Dockerfile
├── frontend/             React + Vite + Tailwind
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── package.json
│   └── Dockerfile
├── agents/               Python + FastAPI + LangGraph
│   ├── orchestrator/     LangGraph state machine
│   ├── review_agent/     6-layer code review
│   ├── test_agent/       Test generation + execution
│   ├── deploy_agent/     Blue/green deployment
│   ├── incident_agent/   Anomaly detection
│   ├── shared/           Common utilities
│   ├── main.py           FastAPI server
│   ├── requirements.txt
│   └── Dockerfile
├── scripts/
│   └── verify-setup.bat  Setup verification
├── docs/                 Architecture and progress logs
├── docker-compose.yml    Multi-service orchestration
├── .env.example          Environment template
├── .gitignore
└── README.md
```

### 5. Configuration (✅)
- `.env.example` created with all required variables documented
- `.gitignore` configured to never commit secrets, build artifacts, or dependencies
- Docker Compose configured for 4 services: frontend, backend, agents, redis

### 6. Documentation (✅)
- Comprehensive setup log in `docs/AgentOps-Setup-Log.md`
- Technical blueprint in `docs/AgentOps-Technical-Blueprint.md`
- This daily progress log

---

## Key Decisions Made

### Why ca-central-1 Region?
Closest AWS region to Toronto, where job applications are targeted. Lower latency for development means faster iteration cycles when testing real-time WebSocket features.

### Why Monorepo Structure?
- Single `git clone` gives developers everything
- Easier dependency management across frontend/backend/agents
- Docker Compose can orchestrate all services from one file
- Better for portfolio — interviewers see the full system at once

### Why FastAPI for Agents (instead of Flask)?
- Built-in async support (critical for concurrent agent execution)
- Automatic OpenAPI docs at `/docs`
- Type hints with Pydantic for safer agent interfaces
- Better performance for high-throughput agent workloads

### Why Socket.io for Real-time?
- Falls back to polling if WebSocket fails (more reliable than raw WebSocket)
- Built-in room/namespace support for multi-pipeline broadcasting
- Excellent React client library

---

## Verification Tests

After running `docker compose up`, verified:

| Service | URL | Expected |
|---------|-----|----------|
| Frontend | http://localhost:3000 | AgentOps landing page with service status |
| Backend health | http://localhost:4000/api/health | JSON: `{"status": "healthy"}` |
| Agents health | http://localhost:5000/health | JSON: `{"status": "healthy"}` |
| Agents API docs | http://localhost:5000/docs | FastAPI auto-generated docs |

---

## Tomorrow (Day 2)

- LangGraph deep dive — build a practice 3-node graph
- Understand StateGraph, nodes, conditional edges
- Implement state persistence with DynamoDB checkpointer
- Goal: Comfortable enough with LangGraph to build the real orchestrator

---

## Notes & Reflections

**On accidentally sharing the Gemini API key:**
This was a great early-career lesson. Even during setup, secrets can leak. Established the discipline of treating credentials as production-sensitive from day one. Going forward: secrets in `.env`, `.env` in `.gitignore`, never in chat or screenshots.

**On the project structure:**
The monorepo with three distinct services (backend, frontend, agents) mirrors real production systems. This matters for interviews — being able to explain "the agents run as separate Python processes that communicate with the Node backend via SQS" demonstrates distributed systems thinking.

**On documentation:**
Capturing decisions and reasoning daily means I can confidently answer "Walk me through your project" in interviews. Each "why" question they ask has an answer in this log.
