import asyncio
from shared.dynamodb_service import get_dynamodb_service

async def go():
    db = get_dynamodb_service()
    await db.save_approval_request(
        "pipe_dashboard_test_soft",
        {"risk_level":"soft","reason":"Coverage dropped below threshold",
         "requires_approval":True,"critical_files":["src/payments.py","src/auth.py"]},
        {"decision":"REQUEST_CHANGES","score":68}
    )
    await db.save_approval_request(
        "pipe_dashboard_test_hard",
        {"risk_level":"hard","reason":"Security: hardcoded API key + new auth flow modified",
         "requires_approval":True,"critical_files":["config/secrets.yaml","src/auth.py","src/api/middleware.py"]},
        {"decision":"REQUEST_CHANGES","score":45}
    )
    print("Seeded 2 approvals")

asyncio.run(go())
