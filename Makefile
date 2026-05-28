# AgentOps test runners
# Usage:
#   make test-agents    Run Python agent tests
#   make test-backend   Run Node backend tests
#   make test-all       Run both

.PHONY: test-agents test-backend test-all

test-agents:
	docker compose exec agents pytest -v

test-backend:
	docker compose exec backend npm test

test-all: test-agents test-backend
	@echo ""
	@echo "All test suites passed."