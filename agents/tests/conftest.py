"""
Pytest fixtures for AgentOps agent tests.

What's mocked:
  - All DynamoDB tables via moto[dynamodb] (in-memory, no AWS calls)
  - HTTP calls to backend (via patched httpx if needed per-test)
  - Gemini API (each test injects its own recorded response)
"""
import sys, os as _os
sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), ".."))
import os
import pytest
import boto3
from moto import mock_aws


# Make tests use a fake AWS region so boto3 doesn't error
os.environ.setdefault("AWS_DEFAULT_REGION", "ca-central-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("GEMINI_API_KEY", "test_key_not_used")


# Map of table_name -> {hash_key, range_key}
TABLE_SCHEMAS = {
    "AgentOps-Pipelines": ("pipeline_id", "created_at"),
    "AgentOps-AgentDecisions": ("pipeline_id", "agent_timestamp"),
    "AgentOps-Approvals": ("pipeline_id", "approval_id"),
    "AgentOps-ApprovalEvents": ("approval_id", "event_timestamp"),
    "AgentOps-Deployments": ("pipeline_id", "deployment_id"),
    "AgentOps-DeploymentEvents": ("deployment_id", "event_timestamp"),
    "AgentOps-Metrics": ("deployment_id", "metric_timestamp"),
    "AgentOps-Incidents": ("deployment_id", "incident_id"),
}


@pytest.fixture
def aws_mock():
    """Spin up a fresh in-memory AWS mock for each test."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="ca-central-1")
        for name, (hk, rk) in TABLE_SCHEMAS.items():
            client.create_table(
                TableName=name,
                AttributeDefinitions=[
                    {"AttributeName": hk, "AttributeType": "S"},
                    {"AttributeName": rk, "AttributeType": "S"},
                ],
                KeySchema=[
                    {"AttributeName": hk, "KeyType": "HASH"},
                    {"AttributeName": rk, "KeyType": "RANGE"},
                ],
                BillingMode="PAY_PER_REQUEST",
            )
        yield client


@pytest.fixture
def db_service(aws_mock):
    """A fresh DynamoDBService backed by moto's in-memory tables."""
    # Force-reset the singleton so it picks up the moto-mocked boto3
    import shared.dynamodb_service as ds
    ds._service = None
    return ds.get_dynamodb_service()


@pytest.fixture
def sample_pr_data():
    """A canonical PR payload for review/test agents."""
    return {
        "pipeline_id": "pipe_test_001",
        "repo": "test-org/test-repo",
        "pr_number": 1,
        "pr_title": "Test PR",
        "pr_author": "test_user",
        "head_sha": "abc123def456",
        "base_sha": "000000",
        "files": [
            {
                "filename": "src/utils.py",
                "status": "modified",
                "additions": 10,
                "deletions": 2,
                "changes": 12,
                "patch": "+def add(a, b):\n+    return a + b",
            }
        ],
        "timestamp": "2026-05-28T12:00:00Z",
    }



@pytest.fixture
def mock_gemini(monkeypatch):
    """
    Patch GeminiClient.generate_json() to return canned fixtures.
    Tests inject a list of responses; calls are returned in order.
    """
    from shared import gemini_client as gc

    class MockGemini:
        def __init__(self):
            self.responses = []
            self.calls = []

        def queue(self, response):
            """Add a response to be returned on the next generate_json call."""
            self.responses.append(response)

        async def generate_json(self, prompt, use_light_model=False, temperature=0.2):
            self.calls.append({"prompt": prompt, "use_light": use_light_model})
            if not self.responses:
                raise RuntimeError(
                    f"MockGemini exhausted. Got {len(self.calls)} calls but no queued response."
                )
            return self.responses.pop(0)

    mock = MockGemini()
    monkeypatch.setattr(gc, "_client", mock)
    monkeypatch.setattr(gc, "get_gemini_client", lambda: mock)
    return mock


@pytest.fixture
def mock_event_emitter(monkeypatch):
    """
    Patch emit_event() so tests don't need a running backend.
    Captures emissions for assertion.
    """
    from shared import event_emitter as ee

    captured = []

    async def fake_emit(channel, type, payload=None, source="agent"):
        captured.append({
            "channel": channel,
            "type": type,
            "payload": payload or {},
            "source": source,
        })
        return True

    monkeypatch.setattr(ee, "emit_event", fake_emit)
    return captured


@pytest.fixture
def mock_github_post(monkeypatch):
    """
    Patch the httpx call that posts GitHub comments via the backend webhook.
    Captures posts for assertion.
    """
    import httpx
    captured = []

    class FakeResponse:
        status_code = 200

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, json=None, **kwargs):
            captured.append({"url": url, "json": json})
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    return captured


@pytest.fixture
def critical_pr_data():
    """PR with security-critical files: hardcoded keys, SQL injection."""
    return {
        "pipeline_id": "pipe_critical_001",
        "repo": "test-org/test-repo",
        "pr_number": 100,
        "pr_title": "Critical PR with hardcoded keys",
        "pr_author": "test_user",
        "head_sha": "critical123abc",
        "base_sha": "000000",
        "files": [
            {
                "filename": "src/utils.py",
                "status": "modified",
                "additions": 20,
                "deletions": 0,
                "changes": 20,
                "patch": (
                    "+API_KEY = 'sk-AKIAIOSFODNN7EXAMPLE'\n"
                    "+def query(user_id):\n"
                    "+    return db.exec(f\"SELECT * FROM u WHERE id={user_id}\")"
                ),
            }
        ],
        "timestamp": "2026-05-28T12:00:00Z",
    }


@pytest.fixture
def clean_pr_data():
    """Low-risk PR: small utility change, no critical paths."""
    return {
        "pipeline_id": "pipe_clean_001",
        "repo": "test-org/test-repo",
        "pr_number": 101,
        "pr_title": "Add helper utility",
        "pr_author": "test_user",
        "head_sha": "clean123abc",
        "base_sha": "000000",
        "files": [
            {
                "filename": "src/helpers.py",
                "status": "modified",
                "additions": 5,
                "deletions": 1,
                "changes": 6,
                "patch": "+def add(a, b):\n+    return a + b",
            }
        ],
        "timestamp": "2026-05-28T12:00:00Z",
    }