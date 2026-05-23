import asyncio, json
from deploy_agent.agent import run_deploy

async def go():
    result = await run_deploy({
        "pipeline_id": "test_deploy_day15",
        "repo": "AryanDeshmukh1/agentops-test-target",
        "pr_number": 1000,
        "head_sha": "day15test5678"
    })
    print("=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))

asyncio.run(go())
