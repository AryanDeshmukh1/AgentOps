import asyncio, json
from deploy_agent.agent import run_deploy

async def go():
    result = await run_deploy({
        "pipeline_id": "test_deploy_day13",
        "repo": "AryanDeshmukh1/agentops-test-target",
        "pr_number": 999,
        "head_sha": "abc123def456"
    })
    print("=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))

asyncio.run(go())
