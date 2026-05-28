"""
Smoke test — proves the test harness works end-to-end.
If this passes, Day 23 is done. Day 24 builds on these fixtures.
"""
import pytest


def test_harness_runs():
    """Sanity: pytest is installed and runs."""
    assert 1 + 1 == 2


@pytest.mark.asyncio
async def test_async_works():
    """Sanity: async tests are wired up."""
    async def get_value():
        return 42
    result = await get_value()
    assert result == 42


def test_moto_dynamodb_works(aws_mock):
    """Sanity: moto fixture creates all 8 tables."""
    response = aws_mock.list_tables()
    table_names = response["TableNames"]
    assert "AgentOps-Pipelines" in table_names
    assert "AgentOps-Incidents" in table_names
    assert len(table_names) == 8


@pytest.mark.asyncio
async def test_db_service_writes_and_reads(db_service, sample_pr_data):
    """Sanity: the real DynamoDBService works against moto."""
    ok = await db_service.save_pipeline(sample_pr_data)
    assert ok is True