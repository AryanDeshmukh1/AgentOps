"""Verify the new mock fixtures work before scaffolding scenario tests."""
import pytest


@pytest.mark.asyncio
async def test_mock_gemini_returns_queued_response(mock_gemini):
    mock_gemini.queue({"findings": [{"severity": "critical"}]})
    from shared.gemini_client import get_gemini_client
    client = get_gemini_client()
    result = await client.generate_json("any prompt")
    assert result == {"findings": [{"severity": "critical"}]}
    assert len(mock_gemini.calls) == 1


@pytest.mark.asyncio
async def test_mock_event_emitter_captures(mock_event_emitter):
    from shared.event_emitter import emit_event
    await emit_event("pipelines", "test.event", {"foo": "bar"})
    assert len(mock_event_emitter) == 1
    assert mock_event_emitter[0]["channel"] == "pipelines"
    assert mock_event_emitter[0]["type"] == "test.event"


@pytest.mark.asyncio
async def test_mock_github_post_captures(mock_github_post):
    import httpx
    async with httpx.AsyncClient() as c:
        resp = await c.post("http://backend:4000/some/url", json={"a": 1})
    assert resp.status_code == 200
    assert len(mock_github_post) == 1


def test_critical_pr_fixture_shape(critical_pr_data):
    assert critical_pr_data["pr_number"] == 100
    assert "API_KEY" in critical_pr_data["files"][0]["patch"]


def test_clean_pr_fixture_shape(clean_pr_data):
    assert clean_pr_data["pr_number"] == 101
    assert "API_KEY" not in clean_pr_data["files"][0]["patch"]