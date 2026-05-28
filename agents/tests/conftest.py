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