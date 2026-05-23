"""
HealthChecker — runs HTTP-based health checks with retries and exponential backoff.

Reusable across DeployAgent (smoke + post-deploy monitoring) and Day 16 (rollback detection).
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import httpx

from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CheckConfig:
    """Configuration for a single health check."""
    name: str
    url: str
    method: str = "GET"
    expected_status: int = 200
    timeout_seconds: float = 5.0
    max_latency_ms: int = 2000
    headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class CheckResult:
    """Result of a single health check execution."""
    name: str
    url: str
    passed: bool
    status_code: Optional[int]
    latency_ms: int
    error: Optional[str]
    attempt: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "passed": self.passed,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "attempt": self.attempt,
        }


class HealthChecker:
    """
    Runs a list of health checks against a target.
    Each check is retried up to max_retries with exponential backoff.
    """

    def __init__(self, checks: List[CheckConfig], max_retries: int = 3, backoff_base_seconds: float = 0.5):
        self.checks = checks
        self.max_retries = max_retries
        self.backoff_base = backoff_base_seconds

    async def run_all(self) -> Dict[str, Any]:
        """Run every check, return aggregate result + per-check details."""
        start_time = time.time()
        results: List[CheckResult] = []

        for check in self.checks:
            result = await self._run_one_with_retry(check)
            results.append(result)

        duration_ms = int((time.time() - start_time) * 1000)
        checks_passed = sum(1 for r in results if r.passed)

        return {
            "status": "ok" if checks_passed == len(results) else "fail",
            "passed": checks_passed == len(results),
            "checks_run": len(results),
            "checks_passed": checks_passed,
            "checks_failed": len(results) - checks_passed,
            "duration_ms": duration_ms,
            "results": [r.to_dict() for r in results],
        }

    async def _run_one_with_retry(self, check: CheckConfig) -> CheckResult:
        """Execute one check with retry + exponential backoff."""
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            result = await self._execute(check, attempt)
            if result.passed:
                return result
            last_error = result.error
            if attempt < self.max_retries:
                backoff = self.backoff_base * (2 ** (attempt - 1))
                logger.warning(
                    f"[HealthCheck] {check.name} attempt {attempt} failed "
                    f"({result.error}). Retrying in {backoff:.1f}s"
                )
                await asyncio.sleep(backoff)

        logger.error(
            f"[HealthCheck] {check.name} FAILED after {self.max_retries} attempts: {last_error}"
        )
        return result

    async def _execute(self, check: CheckConfig, attempt: int) -> CheckResult:
        """Execute a single check attempt."""
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=check.timeout_seconds) as client:
                response = await client.request(
                    method=check.method,
                    url=check.url,
                    headers=check.headers,
                )
                latency_ms = int((time.time() - start) * 1000)

                status_ok = response.status_code == check.expected_status
                latency_ok = latency_ms <= check.max_latency_ms

                if not status_ok:
                    return CheckResult(
                        name=check.name, url=check.url, passed=False,
                        status_code=response.status_code, latency_ms=latency_ms,
                        error=f"Expected status {check.expected_status}, got {response.status_code}",
                        attempt=attempt,
                    )
                if not latency_ok:
                    return CheckResult(
                        name=check.name, url=check.url, passed=False,
                        status_code=response.status_code, latency_ms=latency_ms,
                        error=f"Latency {latency_ms}ms exceeded threshold {check.max_latency_ms}ms",
                        attempt=attempt,
                    )

                return CheckResult(
                    name=check.name, url=check.url, passed=True,
                    status_code=response.status_code, latency_ms=latency_ms,
                    error=None, attempt=attempt,
                )

        except httpx.TimeoutException:
            latency_ms = int((time.time() - start) * 1000)
            return CheckResult(
                name=check.name, url=check.url, passed=False,
                status_code=None, latency_ms=latency_ms,
                error=f"Timeout after {check.timeout_seconds}s",
                attempt=attempt,
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            return CheckResult(
                name=check.name, url=check.url, passed=False,
                status_code=None, latency_ms=latency_ms,
                error=f"{type(e).__name__}: {str(e)[:200]}",
                attempt=attempt,
            )


def default_checks_for_target(base_url: str) -> List[CheckConfig]:
    """Build the standard set of health checks for a newly-deployed slot."""
    return [
        CheckConfig(
            name="health_endpoint",
            url=f"{base_url}/health",
            expected_status=200,
            max_latency_ms=1000,
        ),
        CheckConfig(
            name="deep_health",
            url=f"{base_url}/health/deep",
            expected_status=200,
            max_latency_ms=2000,
        ),
        CheckConfig(
            name="root_responsive",
            url=f"{base_url}/",
            expected_status=200,
            max_latency_ms=1500,
        ),
    ]