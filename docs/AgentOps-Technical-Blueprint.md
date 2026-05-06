# AgentOps — Multi-Agent DevOps Pipeline Orchestrator
## Complete Technical Blueprint

---

## Table of Contents

1. System Overview
2. The 4 AI Agents — Deep Dive
   - Agent 1: ReviewAgent (Code Sentinel)
   - Agent 2: TestAgent (Quality Guardian)
   - Agent 3: DeployAgent (Release Commander)
   - Agent 4: IncidentAgent (Night Watch)
3. The 6 Review Layers — Complete Analysis Framework
   - Layer 1: Security Vulnerability Detection (OWASP Top 10 2025)
   - Layer 2: Code Quality & Clean Code Principles
   - Layer 3: Performance Anti-Pattern Detection
   - Layer 4: Architecture & Design Pattern Compliance
   - Layer 5: Testing Impact Analysis
   - Layer 6: Documentation & Maintainability
4. LangGraph Orchestrator Design
5. Human-in-the-Loop Governance
6. Inter-Agent Communication Protocol
7. Database Schema
8. API Endpoints
9. Dashboard Components
10. Prompt Engineering Templates
11. Scoring Algorithm
12. Build Timeline

---

## 1. System Overview

AgentOps is a multi-agent AI system that autonomously manages CI/CD pipelines. Four specialized AI agents — each with a distinct role — communicate through AWS SQS, share state via DynamoDB, and are orchestrated by a LangGraph directed state graph. A human approval gateway ensures critical actions require sign-off.

### Architecture Diagram

```
GitHub PR Event (Webhook)
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                     NODE.JS BACKEND                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Webhook       │  │ WebSocket    │  │ REST API              │ │
│  │ Receiver      │  │ Server       │  │ /pipelines            │ │
│  │ (GitHub)      │  │ (Dashboard)  │  │ /approvals            │ │
│  └──────┬───────┘  └──────────────┘  │ /incidents            │ │
│         │                             └───────────────────────┘ │
└─────────┼───────────────────────────────────────────────────────┘
          │
          ▼  (SQS Message: "new_pipeline")
┌─────────────────────────────────────────────────────────────────┐
│                   PYTHON AGENT SYSTEM (LangGraph)                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   ORCHESTRATOR GRAPH                     │    │
│  │                                                          │    │
│  │  START ──► ReviewAgent ──► [score >= 70?]               │    │
│  │                               │                          │    │
│  │                    YES ◄──────┴──────► NO ──► END       │    │
│  │                     │                                    │    │
│  │                     ▼                                    │    │
│  │               TestAgent ──► [pass rate >= 80%?]         │    │
│  │                               │                          │    │
│  │                    YES ◄──────┴──────► NO ──► END       │    │
│  │                     │                                    │    │
│  │                     ▼                                    │    │
│  │              ApprovalGate ──► [approved?]                │    │
│  │                               │                          │    │
│  │                    YES ◄──────┴──────► NO ──► END       │    │
│  │                     │                                    │    │
│  │                     ▼                                    │    │
│  │              DeployAgent ──► IncidentAgent ──► END       │    │
│  │                                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ Review   │ │ Test     │ │ Deploy   │ │ Incident         │   │
│  │ Agent    │ │ Agent    │ │ Agent    │ │ Agent            │   │
│  │          │ │          │ │          │ │                   │   │
│  │ 6-Layer  │ │ Generate │ │ Blue/    │ │ Log monitoring   │   │
│  │ Analysis │ │ & Run    │ │ Green    │ │ Anomaly detect   │   │
│  │          │ │ Tests    │ │ Deploy   │ │ Root cause       │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
          │                                        │
          ▼                                        ▼
┌──────────────────┐                    ┌──────────────────┐
│   AWS Services   │                    │  External APIs   │
│                  │                    │                  │
│ • DynamoDB       │                    │ • GitHub API     │
│ • SQS            │                    │ • Gemini API     │
│ • S3             │                    │ • CloudWatch     │
│ • SNS/SES        │                    │                  │
│ • CloudWatch     │                    │                  │
│ • Cognito        │                    │                  │
└──────────────────┘                    └──────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     REACT DASHBOARD                              │
│                                                                  │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────┐ ┌───────────┐ │
│  │ Pipeline    │ │ Agent        │ │ Approval  │ │ Incident  │ │
│  │ Visualizer  │ │ Activity     │ │ Queue     │ │ Timeline  │ │
│  │             │ │ Feed         │ │           │ │           │ │
│  └─────────────┘ └──────────────┘ └───────────┘ └───────────┘ │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────────────┐│
│  │ Metrics     │ │ Agent        │ │ Settings & Config         ││
│  │ Dashboard   │ │ Reasoning    │ │                           ││
│  │ (Recharts)  │ │ Inspector    │ │                           ││
│  └─────────────┘ └──────────────┘ └───────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. The 4 AI Agents — Deep Dive

---

### AGENT 1: ReviewAgent (Code Sentinel)

**Mission:** Analyze every pull request through 6 structured layers and produce a comprehensive, scored code review.

**Trigger:** GitHub webhook fires when a PR is opened, updated, or synchronized.

**Input:**
- PR diff (from GitHub API)
- Full file context (50 lines above/below each change)
- PR description and commit messages
- List of changed files with file types
- Previous review findings (if re-review after fixes)

**Processing Pipeline:**

```
Step 1: FETCH
  ├── GET /repos/{owner}/{repo}/pulls/{pr}/files → list of changed files
  ├── GET /repos/{owner}/{repo}/contents/{path} → full file content for context
  └── Parse diff into structured format: { file, additions[], deletions[], context[] }

Step 2: CLASSIFY
  ├── Determine file types (JS/TS/Python/Java/Config/Docs)
  ├── Calculate change magnitude (lines added/removed)
  └── Assign risk level based on files changed:
       • auth/*, security/*, middleware/* → HIGH RISK
       • migrations/*, schema/* → HIGH RISK
       • tests/*, docs/*, README → LOW RISK
       • everything else → MEDIUM RISK

Step 3: PATTERN SCAN (Deterministic — No AI)
  ├── Regex-based secret detection (API keys, passwords, tokens)
  ├── Known vulnerable patterns (eval(), innerHTML, exec())
  ├── Import analysis (unused imports, circular dependencies)
  └── Output: PatternFindings[] with exact line numbers

Step 4: AI ANALYSIS (LLM-Powered — 6 Layers)
  ├── Construct prompt with diff + context + OWASP rules
  ├── Send to Gemini API (2.5 Flash)
  ├── Parse structured JSON response
  └── Output: AIFindings[] with severity + suggestions

Step 5: MERGE & DEDUPLICATE
  ├── Combine PatternFindings + AIFindings
  ├── Remove duplicates (same file + same line + similar issue)
  ├── Sort by severity (critical → high → medium → low)
  └── Calculate scores per layer

Step 6: REPORT
  ├── Generate structured review report (JSON)
  ├── Post inline comments to GitHub PR via API
  ├── Save to DynamoDB (AgentDecisions table)
  ├── Send result to SQS for TestAgent (if score >= threshold)
  └── Emit WebSocket event for dashboard update
```

**Output Schema:**

```json
{
  "pipeline_id": "pipe_abc123",
  "agent": "ReviewAgent",
  "timestamp": "2026-05-03T10:30:00Z",
  "duration_ms": 4500,
  "tokens_used": 2800,

  "summary": {
    "total_findings": 12,
    "critical": 1,
    "high": 3,
    "medium": 5,
    "low": 3
  },

  "scores": {
    "security": 65,
    "code_quality": 78,
    "performance": 80,
    "architecture": 75,
    "test_impact": 60,
    "documentation": 70,
    "overall": 71
  },

  "decision": "REQUEST_CHANGES",
  "passes_to_next": false,
  "blocking_reason": "1 critical security finding (SQL injection in userController.js:42)",

  "findings": [
    {
      "id": "finding_001",
      "layer": "security",
      "severity": "critical",
      "owasp_category": "A05:2025 - Injection",
      "file": "src/controllers/userController.js",
      "line": 42,
      "title": "NoSQL Injection via unsanitized user input",
      "description": "User-supplied 'username' parameter is passed directly into MongoDB query without sanitization. An attacker could inject query operators like {$gt: ''} to bypass authentication.",
      "vulnerable_code": "const user = await User.findOne({ username: req.body.username });",
      "suggested_fix": "Sanitize input by explicitly casting to string and using mongo-sanitize library.",
      "fix_code": "const sanitize = require('mongo-sanitize');\nconst user = await User.findOne({ username: sanitize(req.body.username) });",
      "confidence": 0.95,
      "detection_method": "ai_analysis"
    }
  ],

  "github_comments_posted": 8,
  "files_analyzed": 5
}
```

---

### AGENT 2: TestAgent (Quality Guardian)

**Mission:** Analyze code changes, generate targeted test cases, execute existing + new tests, and produce a coverage report.

**Trigger:** ReviewAgent completes with overall score >= 70 (configurable).

**Input:**
- ReviewAgent output (findings, changed files, risk areas)
- Full source code of changed files
- Existing test files related to changed code
- Current test configuration (jest.config / pytest.ini)

**Processing Pipeline:**

```
Step 1: IMPACT ANALYSIS
  ├── Map changed files → existing test files
  │   (userController.js → userController.test.js)
  ├── Identify functions that were modified
  ├── Trace call chain: which other functions call the modified ones?
  └── Output: ImpactMap { changedFunctions[], affectedTests[], untestedPaths[] }

Step 2: TEST GENERATION (AI-Powered)
  ├── For each untested code path, generate test cases:
  │   ├── Happy path (valid input → expected output)
  │   ├── Edge cases (empty strings, null, undefined, boundary values)
  │   ├── Error cases (invalid input → proper error handling)
  │   └── Security cases (injection attempts, auth bypass attempts)
  ├── Use ReviewAgent findings to generate regression tests
  │   (e.g., SQL injection finding → test that validates input sanitization)
  └── Output: GeneratedTests[] with test code + description

Step 3: TEST EXECUTION
  ├── Run existing test suite: subprocess('npm test' or 'pytest')
  ├── Run generated tests in isolated environment
  ├── Capture: pass/fail status, execution time, error output
  └── Run coverage tool: subprocess('npx jest --coverage' or 'coverage run')

Step 4: FAILURE ANALYSIS (AI-Powered)
  ├── For each failed test:
  │   ├── Parse error message and stack trace
  │   ├── Send to Gemini with code context
  │   ├── Get root cause analysis + suggested fix
  │   └── Determine if failure is from new code or pre-existing
  └── Output: FailureAnalysis[] with root cause + fix suggestion

Step 5: REPORT
  ├── Generate coverage report (lines, branches, functions)
  ├── Calculate coverage delta (did this PR improve or reduce coverage?)
  ├── Save to DynamoDB
  ├── Send result to SQS for ApprovalGate
  └── Emit WebSocket event
```

**Output Schema:**

```json
{
  "pipeline_id": "pipe_abc123",
  "agent": "TestAgent",
  "timestamp": "2026-05-03T10:32:00Z",
  "duration_ms": 15000,

  "test_execution": {
    "total_tests": 48,
    "passed": 45,
    "failed": 2,
    "skipped": 1,
    "pass_rate": 93.75,
    "execution_time_ms": 8200
  },

  "coverage": {
    "lines": { "current": 82.5, "previous": 80.1, "delta": "+2.4%" },
    "branches": { "current": 71.3, "previous": 70.0, "delta": "+1.3%" },
    "functions": { "current": 88.0, "previous": 86.5, "delta": "+1.5%" }
  },

  "generated_tests": {
    "count": 6,
    "passed": 5,
    "failed": 1,
    "test_files_created": ["tests/generated/userController.gen.test.js"]
  },

  "failures": [
    {
      "test_name": "should reject invalid email format",
      "file": "tests/userController.test.js",
      "error": "Expected status 400 but received 200",
      "root_cause": "Email validation middleware is not applied to the PUT /users/:id route",
      "suggested_fix": "Add validateEmail middleware to the PUT route in userRoutes.js",
      "is_new_regression": true
    }
  ],

  "untested_paths": [
    {
      "file": "src/services/paymentService.js",
      "function": "processRefund",
      "reason": "No test file exists for paymentService"
    }
  ],

  "decision": "PASS",
  "passes_to_next": true
}
```

**Key Technical Details:**

Test Generation Prompt Template:
```python
TEST_GENERATION_PROMPT = """
You are a senior QA engineer. Generate comprehensive test cases
for the following code changes.

CHANGED CODE:
{changed_code}

EXISTING TESTS:
{existing_tests}

REVIEW FINDINGS (from ReviewAgent):
{review_findings}

TESTING FRAMEWORK: {framework} (Jest/pytest)

Generate tests covering:
1. Happy path — valid inputs produce correct outputs
2. Edge cases — boundary values, empty inputs, type coercion
3. Error handling — invalid inputs return proper errors
4. Security — injection attempts are blocked, auth is enforced
5. Regression — specific tests for each ReviewAgent finding

Return JSON:
{
  "tests": [
    {
      "name": "descriptive test name",
      "description": "what this test validates",
      "category": "happy_path|edge_case|error|security|regression",
      "code": "complete runnable test code",
      "targets_finding": "finding_id or null"
    }
  ]
}
"""
```

---

### AGENT 3: DeployAgent (Release Commander)

**Mission:** Execute safe blue/green deployments with health checks, auto-rollback capability, and comprehensive deployment logging.

**Trigger:** TestAgent passes with >= 80% pass rate AND human approval is granted via the Approval Gateway.

**This agent ALWAYS requires human approval before executing.**

**Input:**
- Approved pipeline state
- Deployment configuration (target environment, health check endpoints)
- Current infrastructure state (which environment is "blue" vs "green")

**Processing Pipeline:**

```
Step 1: PRE-DEPLOYMENT CHECKS
  ├── Verify human approval exists in DynamoDB
  ├── Check current infrastructure state
  ├── Validate deployment configuration
  ├── Ensure rollback target is available
  └── Output: PreflightStatus { ready: boolean, blockers[] }

Step 2: BUILD
  ├── Pull latest code from the approved PR branch
  ├── Install dependencies
  ├── Run production build
  ├── Create deployment artifact (Docker image or zip)
  └── Upload artifact to S3

Step 3: DEPLOY TO INACTIVE ENVIRONMENT
  ├── Identify inactive environment (if blue is live → deploy to green)
  ├── Deploy artifact to inactive environment
  ├── Wait for instance/container health
  └── Output: DeploymentTarget { environment, endpoint, status }

Step 4: HEALTH CHECKS
  ├── HTTP health check: GET /health → expect 200
  ├── Deep health check: GET /health/deep → verify DB + cache + external services
  ├── Smoke tests: Hit critical API endpoints with test data
  ├── Response time check: All endpoints respond < 500ms
  └── Run health checks 3 times with 10-second intervals
       If ANY check fails → ABORT and keep old environment live

Step 5: TRAFFIC SWITCH
  ├── Gradually shift traffic: 10% → 25% → 50% → 100% (canary pattern)
  ├── Monitor error rates at each stage
  ├── If error rate > 1% at any stage → ROLLBACK
  └── Once 100% traffic is on new environment → mark as "live"

Step 6: POST-DEPLOYMENT MONITORING (5-minute window)
  ├── Monitor error rate, latency, CPU, memory via CloudWatch
  ├── Compare against baseline metrics (pre-deployment averages)
  ├── If metrics deviate > 2 standard deviations → trigger rollback
  └── After 5 minutes of stable metrics → mark deployment as SUCCESS

Step 7: ROLLBACK (if needed)
  ├── Switch all traffic back to old environment
  ├── Verify old environment is healthy
  ├── Mark deployment as ROLLED_BACK
  ├── Create incident report
  └── Notify team via SNS/SES

Step 8: CLEANUP
  ├── If success: Keep old environment as rollback target for 24 hours
  ├── Log all deployment events to DynamoDB
  ├── Update pipeline status
  └── Hand off to IncidentAgent for continued monitoring
```

**Output Schema:**

```json
{
  "pipeline_id": "pipe_abc123",
  "agent": "DeployAgent",
  "timestamp": "2026-05-03T10:40:00Z",
  "duration_ms": 180000,

  "deployment": {
    "strategy": "blue_green_canary",
    "source_environment": "blue",
    "target_environment": "green",
    "artifact": "s3://agentops-artifacts/pipe_abc123/build.zip",
    "status": "SUCCESS"
  },

  "health_checks": {
    "basic_health": { "passed": true, "response_time_ms": 45 },
    "deep_health": { "passed": true, "response_time_ms": 230 },
    "smoke_tests": { "total": 5, "passed": 5, "failed": 0 }
  },

  "canary_stages": [
    { "traffic_percent": 10, "error_rate": 0.0, "duration_seconds": 30, "status": "passed" },
    { "traffic_percent": 25, "error_rate": 0.1, "duration_seconds": 30, "status": "passed" },
    { "traffic_percent": 50, "error_rate": 0.0, "duration_seconds": 30, "status": "passed" },
    { "traffic_percent": 100, "error_rate": 0.05, "duration_seconds": 300, "status": "passed" }
  ],

  "post_deploy_metrics": {
    "error_rate": { "baseline": 0.1, "current": 0.12, "within_threshold": true },
    "p99_latency_ms": { "baseline": 180, "current": 195, "within_threshold": true },
    "cpu_percent": { "baseline": 35, "current": 38, "within_threshold": true }
  },

  "rollback_available": true,
  "rollback_target": "blue",
  "rollback_expires": "2026-05-04T10:40:00Z",

  "decision": "DEPLOYMENT_SUCCESS",
  "passes_to_next": true
}
```

---

### AGENT 4: IncidentAgent (Night Watch)

**Mission:** Continuously monitor the deployed application post-deployment, detect anomalies, correlate with recent changes, generate incident reports, and recommend or trigger rollbacks.

**Trigger:** DeployAgent marks deployment as SUCCESS. Runs continuously for a configurable monitoring window (default: 1 hour post-deploy, then periodic checks).

**Input:**
- Deployment details (what changed, which environment)
- Baseline metrics (pre-deployment averages)
- CloudWatch log groups and metric namespaces
- Alert thresholds configuration

**Processing Pipeline:**

```
Step 1: BASELINE ESTABLISHMENT
  ├── Query CloudWatch for past 24 hours of metrics
  ├── Calculate: mean, stddev, p50, p95, p99 for:
  │   ├── Error rate (4xx, 5xx responses)
  │   ├── Response latency (p50, p95, p99)
  │   ├── CPU utilization
  │   ├── Memory utilization
  │   ├── Request throughput (requests/second)
  │   └── Active database connections
  └── Store baseline as comparison reference

Step 2: CONTINUOUS MONITORING (Poll every 60 seconds)
  ├── Query CloudWatch Metrics API for current values
  ├── Query CloudWatch Logs Insights for error patterns:
  │   │
  │   │  fields @timestamp, @message, @logStream
  │   │  | filter @message like /ERROR|FATAL|Exception|Unhandled/
  │   │  | sort @timestamp desc
  │   │  | limit 50
  │   │
  ├── Compare current vs baseline using anomaly detection:
  │   ├── Z-score: (current - mean) / stddev
  │   ├── If Z-score > 3.0 → CRITICAL anomaly
  │   ├── If Z-score > 2.0 → WARNING anomaly
  │   └── If Z-score < 2.0 → NORMAL
  └── Output: MetricSnapshot { metrics[], anomalies[] }

Step 3: ANOMALY CORRELATION (AI-Powered)
  When anomaly detected:
  ├── Gather context:
  │   ├── Recent deployment changes (files modified, PRs merged)
  │   ├── Error log samples from the anomaly window
  │   ├── Metric trends (is it getting worse or stabilizing?)
  │   └── Which specific endpoints/services are affected?
  ├── Send to Gemini API with correlation prompt
  ├── Get: root cause hypothesis, confidence score, affected scope
  └── Determine severity: P1 (system down), P2 (degraded), P3 (minor)

Step 4: INCIDENT CREATION
  ├── Generate incident report with:
  │   ├── Timeline of events
  │   ├── Root cause hypothesis
  │   ├── Affected metrics and services
  │   ├── Recommended action (rollback / investigate / monitor)
  │   └── Evidence (log samples, metric graphs data)
  ├── Save to DynamoDB (Incidents table)
  ├── Send alert via SNS (email) and SES (detailed report)
  └── Emit WebSocket event for dashboard

Step 5: AUTO-ROLLBACK RECOMMENDATION
  ├── If severity == P1 AND confidence > 0.8:
  │   └── Recommend IMMEDIATE rollback (requires human approval for hard gate)
  ├── If severity == P2 AND anomaly persists > 5 minutes:
  │   └── Recommend rollback with 10-minute deadline
  ├── If severity == P3:
  │   └── Create ticket, continue monitoring
  └── Dashboard shows rollback button with full context

Step 6: POST-INCIDENT
  ├── If rollback executed → verify recovery metrics
  ├── Generate post-incident summary:
  │   ├── Total incident duration
  │   ├── Mean time to detect (MTTD)
  │   ├── Mean time to recover (MTTR)
  │   ├── Root cause (confirmed or hypothesized)
  │   └── Prevention recommendations
  └── Save summary and close incident
```

**Output Schema:**

```json
{
  "incident_id": "inc_xyz789",
  "pipeline_id": "pipe_abc123",
  "agent": "IncidentAgent",
  "severity": "P2",
  "status": "ACTIVE",

  "detection": {
    "detected_at": "2026-05-03T10:55:00Z",
    "anomaly_type": "error_rate_spike",
    "metric": "5xx_error_rate",
    "baseline_value": 0.1,
    "current_value": 4.7,
    "z_score": 3.8,
    "threshold_breached": "CRITICAL"
  },

  "correlation": {
    "likely_cause": "The NullPointerException in OrderService.processPayment() correlates with the refactored payment validation logic in commit a1b2c3d. The new code path does not handle the case where PaymentGateway returns a null response during timeout.",
    "confidence": 0.85,
    "affected_services": ["order-service", "payment-service"],
    "affected_endpoints": ["POST /api/orders", "POST /api/payments/process"],
    "supporting_evidence": [
      "98% of 5xx errors originate from order-service",
      "Error pattern matches NullPointerException at OrderService.java:142",
      "Errors began exactly 3 minutes after deployment completed",
      "Payment gateway response times are elevated (timeout scenario)"
    ]
  },

  "timeline": [
    { "time": "2026-05-03T10:40:00Z", "event": "Deployment completed to green environment" },
    { "time": "2026-05-03T10:43:00Z", "event": "Traffic fully shifted to green" },
    { "time": "2026-05-03T10:52:00Z", "event": "Error rate began climbing (0.1% → 1.2%)" },
    { "time": "2026-05-03T10:55:00Z", "event": "ANOMALY DETECTED: Error rate 4.7% (Z-score 3.8)" },
    { "time": "2026-05-03T10:55:05Z", "event": "Incident created, rollback recommended" }
  ],

  "recommended_action": "ROLLBACK",
  "rollback_deadline": "2026-05-03T11:05:00Z",

  "post_incident": {
    "mttd_seconds": 720,
    "mttr_seconds": null,
    "prevention": "Add null-check for PaymentGateway response in processPayment(). Add integration test for payment timeout scenario."
  }
}
```

---

## 3. The 6 Review Layers — Complete Analysis Framework

Each layer has specific rules, detection methods, scoring weights, and example patterns. Together they produce the overall review score.

---

### LAYER 1: Security Vulnerability Detection (OWASP Top 10 2025)

**Weight: 30% of overall score** (highest weight — security is non-negotiable)

The OWASP Top 10 2025 categories:

| # | Category | What ReviewAgent Checks |
|---|----------|------------------------|
| A01 | Broken Access Control | Missing auth middleware, IDOR vulnerabilities, privilege escalation, CORS misconfig, direct object references without ownership checks |
| A02 | Security Misconfiguration | Debug mode in production, default credentials, unnecessary features enabled, overly permissive CORS, verbose error messages exposing internals |
| A03 | Software Supply Chain Failures | Dependencies with known CVEs, unpinned versions (using ^ or ~), packages from untrusted sources, missing lock files |
| A04 | Cryptographic Failures | Weak hashing (MD5, SHA1 for passwords), hardcoded encryption keys, missing HTTPS enforcement, weak JWT signing (HS256 with short secret) |
| A05 | Injection | SQL/NoSQL injection (string concatenation in queries), XSS (unsanitized output), OS command injection (exec/spawn with user input), LDAP injection |
| A06 | Insecure Design | Missing rate limiting, no account lockout, predictable resource IDs, missing CSRF protection, no input length limits |
| A07 | Authentication Failures | Weak password policies, missing MFA on sensitive operations, session tokens without proper entropy, missing session timeout |
| A08 | Software & Data Integrity | Unsigned updates, deserialization of untrusted data, CI/CD pipeline without integrity checks, unverified plugins |
| A09 | Security Logging Failures | Missing audit logs for auth events, no alerting on failed logins, sensitive data in logs, insufficient log retention |
| A10 | Mishandling Exceptional Conditions | Empty catch blocks, fail-open error handling, stack traces exposed to users, missing timeout handling, null pointer dereference |

**Detection Methods per Category:**

```
REGEX-BASED (Deterministic, Fast):
├── Hardcoded secrets:
│   ├── /(?:api[_-]?key|secret|password|token)\s*[:=]\s*['"][A-Za-z0-9+/=]{20,}['"]/
│   ├── /(?:AKIA|ASIA)[A-Z0-9]{16}/  (AWS access key)
│   ├── /sk-[a-zA-Z0-9]{48}/  (OpenAI API key)
│   └── /ghp_[a-zA-Z0-9]{36}/  (GitHub personal token)
│
├── Dangerous functions:
│   ├── eval(), Function(), setTimeout(string), setInterval(string)
│   ├── innerHTML, outerHTML, document.write()
│   ├── dangerouslySetInnerHTML (React)
│   ├── exec(), spawn() with unsanitized input
│   └── fs.readFileSync / fs.writeFileSync with user-controlled paths
│
├── SQL/NoSQL injection patterns:
│   ├── String concatenation in queries: `"SELECT * FROM " + table`
│   ├── Template literals in queries: `WHERE id = ${userId}`
│   └── MongoDB without sanitization: `.find({ field: req.body.value })`
│
└── Misconfiguration:
    ├── CORS: Access-Control-Allow-Origin: *
    ├── Debug: NODE_ENV !== 'production' checks missing
    └── HTTPS: http:// URLs for API calls in production code

AI-POWERED (Contextual, Deeper):
├── Business logic vulnerabilities (price manipulation, role escalation)
├── Race conditions in concurrent operations
├── Timing attacks in authentication comparisons
├── Indirect injection paths (input → database → output without sanitization)
├── SSRF via URL parameters passed to internal HTTP clients
└── Insecure deserialization patterns
```

**Scoring:**

```
Critical finding = -25 points (per finding)
High finding     = -10 points (per finding)
Medium finding   = -5 points  (per finding)
Low finding      = -2 points  (per finding)

Starting score: 100
Minimum: 0
Any critical finding → automatic BLOCK (pipeline stops)
```

---

### LAYER 2: Code Quality & Clean Code Principles

**Weight: 20% of overall score**

| Rule | Detection | Threshold | Severity |
|------|-----------|-----------|----------|
| Function too long | Line count per function | > 30 lines | Medium |
| Deep nesting | Indent/bracket depth analysis | > 3 levels | Medium |
| Duplicate code | Similarity matching (AI) | > 10 similar lines | Medium |
| Poor variable names | Pattern match + AI analysis | single char, generic names | Low |
| Magic numbers | Numeric literals in logic | Any non-obvious number | Low |
| Dead code | Unreachable code detection | After return/throw/break | Medium |
| Unused imports | Import vs usage analysis | Any unused import | Low |
| God functions | Functions doing multiple things | Multiple responsibilities | High |
| Missing error handling | try/catch coverage | Async without catch | High |
| Console.log in production | Pattern match | Any console.log | Low |
| Commented-out code | Pattern match | > 3 consecutive commented lines | Low |
| Inconsistent naming | camelCase vs snake_case mix | Mixed conventions | Low |
| Callback hell | Nested callbacks depth | > 3 nested callbacks | Medium |
| Promise anti-patterns | .then() without .catch() | Missing error handling | High |
| Empty catch blocks | catch(e) {} | Empty catch body | High |

**Example Detection:**

```javascript
// BAD — ReviewAgent flags ALL of these:

async function processOrder(req, res) {              // 85 lines long → "Function too long"
  const x = req.body.data;                           // "x" → "Poor variable name"
  if (x) {                                           // Nesting level 1
    if (x.items) {                                   // Nesting level 2
      if (x.items.length > 0) {                      // Nesting level 3
        for (let i = 0; i < x.items.length; i++) {   // Nesting level 4 → "Deep nesting"
          if (x.items[i].price > 0) {                // Nesting level 5 → CRITICAL nesting
            const total = x.items[i].price * 1.13;   // 1.13 → "Magic number (tax rate?)"
            console.log("Processing: " + total);      // console.log → "Remove before production"
            // db.save(total);                         // → "Commented-out code"
          }
        }
      }
    }
  }
}
```

**ReviewAgent Suggestion:**

```javascript
// GOOD — What ReviewAgent suggests:

const TAX_RATE = 0.13;

async function processOrder(req, res) {
  const orderData = validateOrderInput(req.body.data);
  if (!orderData?.items?.length) {
    return res.status(400).json({ error: 'Invalid order data' });
  }

  const processedItems = orderData.items
    .filter(item => item.price > 0)
    .map(item => calculateItemTotal(item));

  await saveOrder(processedItems);
  res.status(200).json({ items: processedItems });
}

function calculateItemTotal(item) {
  return { ...item, total: item.price * (1 + TAX_RATE) };
}
```

**Scoring:**

```
High finding    = -8 points (empty catch, missing error handling)
Medium finding  = -4 points (long functions, deep nesting)
Low finding     = -2 points (naming, magic numbers, console.log)

Starting score: 100
```

---

### LAYER 3: Performance Anti-Pattern Detection

**Weight: 15% of overall score**

| Anti-Pattern | What to Detect | Example | Fix |
|---|---|---|---|
| N+1 Query | DB calls inside loops | `for (user of users) { await db.find(user.id) }` | Batch: `db.find({ _id: { $in: userIds } })` |
| Missing Pagination | find() without limit | `Collection.find({})` | Add `.limit(20).skip(offset)` |
| Memory Leaks | Listeners without cleanup | `addEventListener` without `removeEventListener` | Cleanup in useEffect return / componentWillUnmount |
| Sync I/O in Async | readFileSync in handlers | `fs.readFileSync(path)` in API handler | Use `fs.promises.readFile(path)` |
| Missing Caching | Repeated expensive calls | Same API call in every request | Add Redis/in-memory cache with TTL |
| Large Payloads | Full object in response | `res.json(fullUserObject)` | Select specific fields: `{ name, email }` |
| Unnecessary Re-renders | Missing memoization | Component re-renders on every parent update | `React.memo()`, `useMemo()`, `useCallback()` |
| Blocking Event Loop | CPU-heavy in main thread | Sorting 100K records synchronously | Worker thread or pagination |
| Missing Indexes | Queries on unindexed fields | `find({ email: ... })` without email index | Create database index |
| Connection Leaks | DB connections not released | Opening connection without closing in finally | Use connection pooling or try/finally |
| Unbounded Loops | Loops without termination guarantee | `while(true)` without break condition | Add maximum iteration limit |
| Missing Compression | Large response bodies | 500KB JSON responses without gzip | Enable compression middleware |

**Scoring:**

```
High finding    = -10 points (N+1 query, memory leak, connection leak)
Medium finding  = -5 points  (missing pagination, sync I/O, no caching)
Low finding     = -3 points  (missing compression, unnecessary re-renders)

Starting score: 100
```

---

### LAYER 4: Architecture & Design Pattern Compliance

**Weight: 15% of overall score**

| Pattern | What to Check | Bad Example | Good Example |
|---|---|---|---|
| Separation of Concerns | Business logic in route handlers | `router.post('/users', async (req, res) => { /* 50 lines of DB + validation + email */ })` | Route → Controller → Service → Repository layers |
| REST Conventions | Wrong HTTP methods, inconsistent URLs | `POST /getUsers`, `GET /deleteUser/1` | `GET /users`, `DELETE /users/1` |
| Error Response Consistency | Mixed error formats | Some: `{error: "msg"}`, Others: `{message: "msg", code: 500}` | Unified: `{ success: false, error: { code, message } }` |
| Middleware Usage | Auth/validation duplicated in routes | Auth check copy-pasted in every handler | `router.use(authMiddleware)` applied to route group |
| Circular Dependencies | A imports B, B imports A | Module A ← → Module B | Introduce interface or event-based decoupling |
| Hardcoded Config | URLs, ports, flags in code | `const DB_URL = 'mongodb://localhost:27017'` | `process.env.DB_URL` with .env file |
| Single Responsibility | Classes/modules doing too much | `UserService` handles auth + email + billing + logging | Split into `AuthService`, `EmailService`, `BillingService` |
| Dependency Injection | Hard-coded dependencies | `const db = new MongoDB()` inside service | Pass db as constructor parameter |
| API Versioning | No versioning on public APIs | `/api/users` | `/api/v1/users` |
| Status Codes | Wrong HTTP status codes | Returning 200 for errors, 500 for validation | 400 for validation, 401 for auth, 404 for not found |

**Scoring:**

```
High finding    = -10 points (circular dependencies, no separation of concerns)
Medium finding  = -5 points  (wrong status codes, hardcoded config)
Low finding     = -3 points  (missing API versioning, inconsistent naming)

Starting score: 100
```

---

### LAYER 5: Testing Impact Analysis

**Weight: 10% of overall score**

| Check | Description | Severity |
|---|---|---|
| New code without tests | Lines added that have zero test coverage | High |
| Modified function signature | Function params changed → existing tests likely broken | High |
| Changed return type | Return value changed → assertions will fail | High |
| Deleted test | Test file or test case removed without explanation | Critical |
| Reduced coverage | PR decreases overall test coverage percentage | Medium |
| Untestable code | Tightly coupled code that can't be unit tested | Medium |
| Test quality | Tests that just check truthy/falsy without meaningful assertions | Low |
| Missing integration test | API endpoint added without integration test | Medium |
| Flaky test indicators | Test depends on timing, external services, or order | Low |
| Missing edge case tests | Only happy path tested, no error scenarios | Medium |

**Scoring:**

```
Critical finding = -20 points (deleted tests without reason)
High finding     = -10 points (new code without tests, broken signatures)
Medium finding   = -5 points  (reduced coverage, missing integration tests)
Low finding      = -3 points  (test quality, flaky indicators)

Starting score: 100
```

---

### LAYER 6: Documentation & Maintainability

**Weight: 10% of overall score**

| Check | Description | Severity |
|---|---|---|
| Missing function docs | Public functions without JSDoc/docstring | Medium |
| Missing API docs | New endpoint without documentation | High |
| Outdated comments | Comments that don't match the code behavior | Medium |
| Missing README update | New feature/config without README change | Low |
| Complex logic undocumented | Regex, algorithms, business rules without explanation | High |
| Missing changelog entry | Breaking change without changelog note | Medium |
| TODO/FIXME/HACK markers | Temporary code shipped to production | Low |
| Missing type annotations | Functions without parameter/return types (TypeScript) | Low |
| Unclear error messages | Error strings that don't help debugging | Low |
| Missing environment docs | New env variable without documentation | Medium |

**Scoring:**

```
High finding    = -8 points
Medium finding  = -4 points
Low finding     = -2 points

Starting score: 100
```

---

### Overall Score Calculation

```
Overall Score = (Security × 0.30) +
               (CodeQuality × 0.20) +
               (Performance × 0.15) +
               (Architecture × 0.15) +
               (TestImpact × 0.10) +
               (Documentation × 0.10)

Decision Logic:
  Score >= 85  → AUTO_APPROVE (low risk, proceed)
  Score 70-84  → PASS_WITH_WARNINGS (proceed, but flag issues)
  Score 50-69  → REQUEST_CHANGES (block, must fix)
  Score < 50   → REJECT (significant issues, needs rework)

  ANY critical security finding → BLOCK regardless of score
```

---

## 4. LangGraph Orchestrator Design

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict, Optional

class PipelineState(TypedDict):
    pipeline_id: str
    repo: str
    pr_number: int
    pr_author: str
    risk_level: str                           # auto | soft | hard

    # Agent outputs
    review_result: Optional[dict]             # ReviewAgent output
    test_result: Optional[dict]               # TestAgent output
    approval_status: Optional[str]            # approved | rejected | pending
    deploy_result: Optional[dict]             # DeployAgent output
    incident_result: Optional[dict]           # IncidentAgent output

    # Flow control
    current_agent: str
    status: str                               # running | completed | failed | rolled_back
    error: Optional[str]
    messages: list                            # WebSocket broadcast queue


def should_proceed_to_test(state: PipelineState) -> str:
    """Conditional edge after ReviewAgent"""
    score = state["review_result"]["scores"]["overall"]
    has_critical = state["review_result"]["summary"]["critical"] > 0

    if has_critical:
        return "blocked_critical"
    if score >= 70:
        return "proceed_to_test"
    return "blocked_low_score"


def should_proceed_to_approval(state: PipelineState) -> str:
    """Conditional edge after TestAgent"""
    pass_rate = state["test_result"]["test_execution"]["pass_rate"]

    if pass_rate >= 80:
        return "proceed_to_approval"
    return "blocked_test_failure"


def should_proceed_to_deploy(state: PipelineState) -> str:
    """Conditional edge after Approval Gate"""
    if state["approval_status"] == "approved":
        return "proceed_to_deploy"
    return "blocked_not_approved"


# Build the graph
graph = StateGraph(PipelineState)

# Add nodes
graph.add_node("review_agent", run_review_agent)
graph.add_node("test_agent", run_test_agent)
graph.add_node("approval_gate", check_approval)
graph.add_node("deploy_agent", run_deploy_agent)
graph.add_node("incident_agent", run_incident_agent)
graph.add_node("notify_blocked", send_block_notification)
graph.add_node("notify_success", send_success_notification)

# Define edges
graph.set_entry_point("review_agent")

graph.add_conditional_edges("review_agent", should_proceed_to_test, {
    "proceed_to_test": "test_agent",
    "blocked_critical": "notify_blocked",
    "blocked_low_score": "notify_blocked",
})

graph.add_conditional_edges("test_agent", should_proceed_to_approval, {
    "proceed_to_approval": "approval_gate",
    "blocked_test_failure": "notify_blocked",
})

graph.add_conditional_edges("approval_gate", should_proceed_to_deploy, {
    "proceed_to_deploy": "deploy_agent",
    "blocked_not_approved": "notify_blocked",
})

graph.add_edge("deploy_agent", "incident_agent")
graph.add_edge("incident_agent", "notify_success")
graph.add_edge("notify_blocked", END)
graph.add_edge("notify_success", END)

# Compile
pipeline = graph.compile()
```

---

## 5. Human-in-the-Loop Governance

### Risk Classification System

```
AUTO-APPROVE (No human needed):
  ├── Only documentation files changed (.md, .txt, .rst)
  ├── Only test files changed
  ├── Only style/formatting changes (CSS, whitespace)
  ├── ReviewAgent score >= 90
  └── All changes in low-risk directories

SOFT-APPROVE (Human notified, 15-min veto window):
  ├── Feature additions (new endpoints, new components)
  ├── Non-breaking API changes
  ├── Dependency updates (patch/minor versions)
  ├── ReviewAgent score 75-89
  └── Changes in medium-risk directories

HARD-APPROVE (Pipeline pauses, explicit approval required):
  ├── Database migrations or schema changes
  ├── Authentication/authorization code changes
  ├── Infrastructure configuration changes
  ├── Breaking API changes
  ├── Dependency updates (major versions)
  ├── Changes to security-related files
  ├── ReviewAgent score < 75
  └── Any critical finding from any agent
```

### Approval Dashboard UI Components

```
┌─────────────────────────────────────────────────────────────┐
│ APPROVAL QUEUE                                    2 pending │
│                                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ 🔴 HARD APPROVAL REQUIRED                              │ │
│ │                                                         │ │
│ │ PR #142: "Refactor auth middleware"                     │ │
│ │ Author: @aryan-dev  ·  Changed: 8 files  ·  +210 -45  │ │
│ │                                                         │ │
│ │ Risk Factor: Authentication code modified               │ │
│ │                                                         │ │
│ │ ReviewAgent Score: 72/100                               │ │
│ │ ├── Security: 65 ⚠️  (1 high finding)                  │ │
│ │ ├── Quality: 78                                         │ │
│ │ └── Tests: 85 ✅                                        │ │
│ │                                                         │ │
│ │ TestAgent: 45/48 passing (93.75%) ✅                    │ │
│ │ Coverage delta: +2.4%                                   │ │
│ │                                                         │ │
│ │ Agent Recommendation: APPROVE WITH CAUTION              │ │
│ │ Reasoning: "High finding is a missing rate limiter on   │ │
│ │ the new /auth/reset-password endpoint. The endpoint     │ │
│ │ works correctly but could be brute-forced without       │ │
│ │ rate limiting. Non-blocking but should be addressed."   │ │
│ │                                                         │ │
│ │ [View Full Review]  [View Test Results]                 │ │
│ │                                                         │ │
│ │ [✅ APPROVE]  [❌ REJECT]  [💬 Request Changes]        │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 6. Inter-Agent Communication Protocol

All agents communicate via AWS SQS with a standardized message format:

```json
{
  "message_id": "msg_unique_id",
  "pipeline_id": "pipe_abc123",
  "source_agent": "ReviewAgent",
  "target_agent": "TestAgent",
  "timestamp": "2026-05-03T10:30:00Z",
  "action": "PROCEED",
  "payload": {
    "review_score": 72,
    "risk_level": "hard",
    "changed_files": ["src/auth/middleware.js", "src/routes/users.js"],
    "findings_summary": { "critical": 0, "high": 1, "medium": 3, "low": 2 },
    "test_priorities": [
      { "file": "src/auth/middleware.js", "reason": "Auth code changed, high-risk", "priority": 1 },
      { "file": "src/routes/users.js", "reason": "New endpoint added without tests", "priority": 2 }
    ]
  }
}
```

### SQS Queue Architecture

```
Queues:
  agentops-review-queue      ← GitHub webhook triggers ReviewAgent
  agentops-test-queue        ← ReviewAgent sends to TestAgent
  agentops-approval-queue    ← TestAgent sends to ApprovalGate
  agentops-deploy-queue      ← Approval triggers DeployAgent
  agentops-incident-queue    ← DeployAgent triggers IncidentAgent
  agentops-dead-letter-queue ← Failed messages go here for debugging
```

---

## 7. Database Schema (DynamoDB)

### Table: Pipelines

```
Partition Key: pipeline_id (String)
Sort Key: created_at (String - ISO 8601)

Attributes:
  repo                    String    "owner/repo-name"
  pr_number               Number    142
  pr_author               String    "aryan-dev"
  pr_title                String    "Refactor auth middleware"
  status                  String    "running|completed|failed|rolled_back|blocked"
  current_agent           String    "ReviewAgent|TestAgent|DeployAgent|IncidentAgent"
  risk_level              String    "auto|soft|hard"
  review_score            Number    72
  test_pass_rate          Number    93.75
  deployment_status       String    "success|failed|rolled_back"
  started_at              String    ISO 8601
  completed_at            String    ISO 8601
  total_duration_ms       Number    245000
  total_tokens_used       Number    8500

GSI: status-index (status → created_at) for querying active pipelines
GSI: repo-index (repo → created_at) for per-repo history
```

### Table: AgentDecisions

```
Partition Key: pipeline_id (String)
Sort Key: agent_name#timestamp (String)

Attributes:
  agent_type              String    "review|test|deploy|incident"
  input_summary           String    Brief description of what agent received
  output                  Map       Full agent output (JSON)
  scores                  Map       { security: 65, quality: 78, ... }
  decision                String    "approve|reject|escalate|rollback"
  confidence              Number    0.85
  reasoning               String    "Why the agent made this decision"
  duration_ms             Number    4500
  tokens_used             Number    2800
  findings_count          Map       { critical: 0, high: 1, medium: 3, low: 2 }
```

### Table: Approvals

```
Partition Key: pipeline_id (String)
Sort Key: approval_id (String)

Attributes:
  requested_at            String    ISO 8601
  risk_level              String    "auto|soft|hard"
  agent_recommendation    String    "approve|reject"
  agent_reasoning         String    "Missing rate limiter on..."
  human_decision          String    "approved|rejected|pending"
  human_id                String    Cognito user ID
  decided_at              String    ISO 8601
  override_reason         String    If human disagrees with agent
  veto_deadline           String    ISO 8601 (for soft-approve)
```

### Table: Incidents

```
Partition Key: incident_id (String)
Sort Key: created_at (String)

Attributes:
  pipeline_id             String    "pipe_abc123"
  severity                String    "P1|P2|P3"
  status                  String    "active|mitigated|resolved|false_positive"
  anomaly_type            String    "error_rate_spike|latency_spike|memory_leak|..."
  detection               Map       { metric, baseline, current, z_score }
  correlation             Map       { likely_cause, confidence, affected_services }
  timeline                List      [{ time, event }]
  recommended_action      String    "rollback|investigate|monitor"
  rollback_executed       Boolean   false
  resolved_at             String    ISO 8601
  mttd_seconds            Number    Mean time to detect
  mttr_seconds            Number    Mean time to recover
  post_mortem             String    Summary and prevention recommendations
```

### Table: Metrics

```
Partition Key: repo (String)
Sort Key: date (String)

Attributes:
  total_pipelines         Number
  successful_deploys      Number
  failed_deploys          Number
  rollbacks               Number
  avg_review_score        Number
  avg_test_pass_rate      Number
  avg_pipeline_duration   Number
  incidents_detected      Number
  avg_mttd               Number
  avg_mttr               Number
  human_overrides         Number    Times human disagreed with agent
```

---

## 8. API Endpoints

### Backend REST API

```
PIPELINES
  POST   /api/webhooks/github          GitHub webhook receiver
  GET    /api/pipelines                 List all pipelines (paginated)
  GET    /api/pipelines/:id             Get pipeline details + agent outputs
  GET    /api/pipelines/:id/timeline    Get pipeline event timeline
  POST   /api/pipelines/:id/retry       Retry failed pipeline

APPROVALS
  GET    /api/approvals/pending         List pending approvals
  POST   /api/approvals/:id/approve     Approve a pipeline
  POST   /api/approvals/:id/reject      Reject a pipeline
  POST   /api/approvals/:id/veto        Veto a soft-approved pipeline

INCIDENTS
  GET    /api/incidents                 List all incidents
  GET    /api/incidents/:id             Get incident details
  POST   /api/incidents/:id/rollback    Trigger rollback
  POST   /api/incidents/:id/resolve     Mark incident resolved
  POST   /api/incidents/:id/false-alarm Mark as false positive

METRICS
  GET    /api/metrics/overview          Dashboard metrics (deploy freq, MTTR, etc.)
  GET    /api/metrics/agents            Per-agent performance stats
  GET    /api/metrics/trends            Historical trend data for charts

CONFIG
  GET    /api/config                    Get current thresholds
  PUT    /api/config                    Update thresholds (score gates, alert levels)

AUTH
  POST   /api/auth/login                Cognito authentication
  GET    /api/auth/me                   Current user profile
```

### WebSocket Events (Socket.io)

```
Server → Client:
  pipeline:created        New pipeline started
  pipeline:updated        Pipeline status changed
  agent:started           Agent began processing
  agent:progress          Agent intermediate update (e.g., "Analyzing file 3/8...")
  agent:completed         Agent finished with results
  approval:requested      New approval needed
  approval:resolved       Approval granted or rejected
  incident:detected       New incident detected
  incident:updated        Incident status changed
  deploy:progress         Deployment stage update (10% → 25% → 50% → 100%)
```

---

## 9. Dashboard Components (React)

### Component Tree

```
App.jsx
├── Layout.jsx
│   ├── Sidebar.jsx (navigation)
│   └── Header.jsx (user info, notifications bell)
│
├── Pages/
│   ├── DashboardPage.jsx
│   │   ├── MetricsCards.jsx (deploy count, success rate, avg MTTR)
│   │   ├── ActivePipelines.jsx (currently running pipelines)
│   │   ├── RecentActivity.jsx (latest agent decisions)
│   │   └── TrendCharts.jsx (Recharts: deploys/week, scores over time)
│   │
│   ├── PipelinePage.jsx
│   │   ├── PipelineVisualizer.jsx (visual graph: nodes = agents, edges = flow)
│   │   ├── AgentActivityFeed.jsx (real-time log of agent actions)
│   │   ├── AgentDetailPanel.jsx (expand to see full reasoning + findings)
│   │   ├── ReviewFindings.jsx (categorized findings with code snippets)
│   │   ├── TestResults.jsx (pass/fail with coverage delta)
│   │   └── DeployTimeline.jsx (stage-by-stage deployment progress)
│   │
│   ├── ApprovalsPage.jsx
│   │   ├── ApprovalQueue.jsx (pending approvals with full context)
│   │   ├── ApprovalDetail.jsx (agent recommendation + reasoning)
│   │   └── ApprovalHistory.jsx (past decisions, overrides)
│   │
│   ├── IncidentsPage.jsx
│   │   ├── ActiveIncidents.jsx (current incidents with severity)
│   │   ├── IncidentTimeline.jsx (event-by-event breakdown)
│   │   ├── IncidentCorrelation.jsx (AI root cause analysis display)
│   │   └── RollbackControl.jsx (one-click rollback with confirmation)
│   │
│   └── SettingsPage.jsx
│       ├── ThresholdConfig.jsx (score gates, alert levels)
│       ├── NotificationConfig.jsx (email, Slack webhook)
│       └── RepositoryConfig.jsx (connected repos, branch rules)
│
└── Hooks/
    ├── useWebSocket.js (Socket.io connection + event handlers)
    ├── usePipeline.js (pipeline data fetching + caching)
    └── useAuth.js (Cognito auth state)
```

---

## 10. Prompt Engineering Templates

### ReviewAgent Security Prompt

```python
SECURITY_PROMPT = """
You are a senior application security engineer performing a code review.
Your review MUST be based on the OWASP Top 10 2025 standard.

OWASP TOP 10 2025:
A01: Broken Access Control — missing auth, IDOR, privilege escalation, SSRF
A02: Security Misconfiguration — debug enabled, default creds, verbose errors
A03: Software Supply Chain — vulnerable deps, unpinned versions, untrusted packages
A04: Cryptographic Failures — weak hashing, hardcoded keys, missing HTTPS
A05: Injection — SQL/NoSQL/OS/XSS injection via unsanitized input
A06: Insecure Design — missing rate limits, predictable IDs, no CSRF
A07: Authentication Failures — weak passwords, no MFA, session issues
A08: Data Integrity — unsigned updates, unsafe deserialization
A09: Logging Failures — missing audit logs, no alerting, sensitive data in logs
A10: Exceptional Conditions — empty catch, fail-open, exposed stack traces

DIFF TO REVIEW:
```
{diff_content}
```

FULL FILE CONTEXT (surrounding code):
```
{file_context}
```

CHANGED FILES: {changed_files}

Analyze EVERY line in the diff. For each security issue found, respond
with this exact JSON structure. Do NOT include any text outside the JSON.

{{
  "findings": [
    {{
      "severity": "critical|high|medium|low",
      "owasp_category": "A01-A10",
      "cwe_id": "CWE-XXX if known",
      "file": "exact/file/path.js",
      "line": <line_number>,
      "title": "Short descriptive title",
      "description": "Detailed explanation of the vulnerability and attack vector",
      "vulnerable_code": "the exact code that is vulnerable",
      "attack_scenario": "How an attacker would exploit this",
      "suggested_fix": "Description of the fix",
      "fix_code": "The corrected code",
      "confidence": <0.0-1.0>
    }}
  ],
  "security_score": <0-100>,
  "summary": "One paragraph overall security assessment"
}}
"""
```

### TestAgent Generation Prompt

```python
TEST_GEN_PROMPT = """
You are a senior QA engineer. Generate comprehensive test cases.

CODE UNDER TEST:
```
{source_code}
```

FUNCTION SIGNATURES CHANGED:
{changed_functions}

EXISTING TESTS:
```
{existing_tests}
```

SECURITY FINDINGS FROM REVIEW:
{security_findings}

TESTING FRAMEWORK: {framework}

Generate tests for ALL of these categories:
1. HAPPY PATH — Valid inputs produce correct outputs
2. EDGE CASES — Empty strings, null, undefined, 0, negative, MAX_INT, Unicode
3. ERROR HANDLING — Invalid inputs return proper error codes and messages
4. SECURITY — Injection attempts blocked, auth enforced, rate limits work
5. REGRESSION — One test per security finding to verify the fix works
6. BOUNDARY — Values at exact limits (min, max, min-1, max+1)

Return ONLY valid JSON:
{{
  "tests": [
    {{
      "name": "should reject SQL injection in username field",
      "category": "security",
      "description": "Verifies that SQL injection characters are sanitized",
      "targets_file": "src/controllers/userController.js",
      "targets_function": "createUser",
      "targets_finding_id": "finding_001 or null",
      "code": "complete runnable test code as a string",
      "expected_behavior": "Returns 400 with validation error"
    }}
  ]
}}
"""
```

### IncidentAgent Correlation Prompt

```python
CORRELATION_PROMPT = """
You are a senior SRE investigating a production incident.

ANOMALY DETECTED:
- Metric: {metric_name}
- Baseline (24h average): {baseline_value}
- Current value: {current_value}
- Z-score: {z_score}
- Duration: anomaly started {minutes_ago} minutes ago

RECENT DEPLOYMENT (occurred {deploy_minutes_ago} minutes ago):
- Changed files: {changed_files}
- Commit messages: {commit_messages}
- PR description: {pr_description}
- ReviewAgent findings: {review_findings}

ERROR LOGS (last 50 entries):
```
{error_logs}
```

SYSTEM METRICS:
- CPU: {cpu_current}% (baseline: {cpu_baseline}%)
- Memory: {memory_current}% (baseline: {memory_baseline}%)
- Active DB connections: {db_conn_current} (baseline: {db_conn_baseline})
- Request throughput: {rps_current} req/s (baseline: {rps_baseline} req/s)

Analyze and respond with ONLY this JSON:
{{
  "root_cause_hypothesis": "Detailed explanation of what is likely causing the anomaly",
  "confidence": <0.0-1.0>,
  "severity": "P1|P2|P3",
  "affected_services": ["list", "of", "services"],
  "affected_endpoints": ["list", "of", "API", "endpoints"],
  "correlation_with_deployment": "strong|moderate|weak|none",
  "evidence": ["list of supporting evidence points"],
  "recommended_action": "rollback|investigate|monitor",
  "action_reasoning": "Why this action is recommended",
  "prevention_suggestions": ["How to prevent this in the future"]
}}
"""
```

---

## 11. Scoring Algorithm

```python
def calculate_overall_score(layer_scores: dict) -> dict:
    """
    Weighted scoring across all 6 layers.
    Returns overall score and decision.
    """
    weights = {
        "security":      0.30,
        "code_quality":  0.20,
        "performance":   0.15,
        "architecture":  0.15,
        "test_impact":   0.10,
        "documentation": 0.10,
    }

    overall = sum(
        layer_scores[layer] * weight
        for layer, weight in weights.items()
    )

    overall = max(0, min(100, round(overall, 1)))

    # Decision logic
    if layer_scores.get("has_critical_security", False):
        decision = "BLOCK"
        reason = "Critical security vulnerability detected"
    elif overall >= 85:
        decision = "AUTO_APPROVE"
        reason = "High confidence, low risk"
    elif overall >= 70:
        decision = "PASS_WITH_WARNINGS"
        reason = "Acceptable but has areas for improvement"
    elif overall >= 50:
        decision = "REQUEST_CHANGES"
        reason = "Multiple issues need to be addressed"
    else:
        decision = "REJECT"
        reason = "Significant issues require rework"

    return {
        "overall_score": overall,
        "layer_scores": layer_scores,
        "weights": weights,
        "decision": decision,
        "reason": reason,
        "passes_to_next_agent": decision in ["AUTO_APPROVE", "PASS_WITH_WARNINGS"]
    }
```

---

## 12. Build Timeline (4 Weeks)

### Week 1: Foundation + ReviewAgent

```
Day 1-2: Project setup
  ├── Monorepo structure (frontend/ backend/ agents/)
  ├── Docker Compose for local development
  ├── AWS account setup + $1 budget alert
  ├── DynamoDB tables created
  ├── Basic Node.js server with health endpoint

Day 3-4: GitHub integration + ReviewAgent core
  ├── GitHub webhook receiver (PR events)
  ├── GitHub API client (fetch diffs, post comments)
  ├── ReviewAgent: regex-based pattern scanner (Layer 1 deterministic)
  ├── ReviewAgent: Gemini API integration for AI analysis

Day 5-7: ReviewAgent complete + Dashboard shell
  ├── All 6 layers implemented in ReviewAgent
  ├── Scoring algorithm
  ├── GitHub PR comment posting
  ├── React dashboard shell with routing
  ├── WebSocket connection (Socket.io)
  ├── Basic pipeline list view
```

### Week 2: TestAgent + LangGraph Orchestrator

```
Day 8-9: TestAgent
  ├── Impact analysis (changed files → test files mapping)
  ├── Test generation via Gemini API
  ├── Test execution via subprocess
  ├── Coverage report parsing
  ├── Failure analysis

Day 10-11: LangGraph orchestrator
  ├── State graph definition
  ├── Conditional edges (score thresholds)
  ├── State persistence to DynamoDB
  ├── SQS integration for inter-agent messaging

Day 12-14: Dashboard - Pipeline View
  ├── Pipeline visualizer (agent nodes + flow)
  ├── Agent activity feed (real-time)
  ├── Review findings display (categorized)
  ├── Test results display (pass/fail + coverage)
```

### Week 3: DeployAgent + IncidentAgent + Approvals

```
Day 15-16: Human Approval Gateway
  ├── Approval queue API
  ├── Risk classification system
  ├── Dashboard: approval queue with full context
  ├── Approve/reject/veto actions

Day 17-18: DeployAgent
  ├── Blue/green deployment logic
  ├── Health check system
  ├── Canary traffic shifting (simulated)
  ├── Auto-rollback on failure

Day 19-21: IncidentAgent
  ├── CloudWatch integration
  ├── Baseline establishment
  ├── Anomaly detection (Z-score)
  ├── Gemini-powered correlation analysis
  ├── Incident report generation
  ├── Dashboard: incident timeline + rollback control
```

### Week 4: Polish + Deploy + Document

```
Day 22-23: Metrics Dashboard
  ├── Recharts: deployment frequency over time
  ├── Recharts: average review scores trend
  ├── Recharts: MTTD/MTTR trends
  ├── Agent accuracy metrics
  ├── Human override tracking

Day 24-25: AWS Deployment
  ├── Lambda functions for agents
  ├── API Gateway for backend
  ├── Vercel for frontend
  ├── GitHub Actions CI/CD pipeline
  ├── CloudWatch alarms + SNS alerts

Day 26-27: Testing + Documentation
  ├── Integration tests for full pipeline flow
  ├── README with architecture diagrams
  ├── API documentation
  ├── Demo video recording
  ├── Resume bullet points finalized

Day 28: Final polish
  ├── Error handling edge cases
  ├── Loading states in dashboard
  ├── Mobile responsiveness
  ├── Performance optimization
```

---

## Resume Bullets (Final)

**AgentOps — Multi-Agent DevOps Pipeline Orchestrator**
*(React, Node.js, Python, LangGraph, AWS Lambda, SQS, DynamoDB, CloudWatch, Gemini API, Docker)*

- Architected a multi-agent AI system using LangGraph with 4 specialized agents (code review, test generation, deployment, incident response) communicating via SQS with checkpoint persistence in DynamoDB.

- Implemented 6-layer code review analysis covering OWASP Top 10 2025 security scanning, clean code detection, performance anti-patterns, architecture compliance, test impact analysis, and documentation coverage, producing weighted scores with configurable thresholds.

- Built human-in-the-loop governance with tiered approval gates (auto/soft/hard) based on AI-assessed risk classification, ensuring safe autonomous operations for CI/CD workflows.

- Developed real-time monitoring with Z-score anomaly detection and LLM-powered incident correlation, achieving automated root cause analysis with mean time to detect under 3 minutes.

- Deployed as serverless cloud-native application on AWS (Lambda, API Gateway, DynamoDB, SQS, S3, CloudWatch, Cognito) with CI/CD via GitHub Actions and React dashboard on Vercel.
