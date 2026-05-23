"""
TrafficShifter — gradually moves traffic from blue to green with health gating.

Default progression: 10% -> 50% -> 100% green, each step health-checked.
On a check failure mid-shift, halts at current split (Day 16 handles rollback).
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Awaitable

from deploy_agent.health_checker import HealthChecker
from shared.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ShiftStep:
    """One step in the traffic-shift progression."""
    green_percent: int
    dwell_seconds: float = 2.0  # how long to wait after shift before health-checking


@dataclass
class ShiftResult:
    """Result of a single traffic-shift step."""
    step_number: int
    blue_percent: int
    green_percent: int
    health_passed: bool
    health_summary: Dict[str, Any]
    duration_ms: int
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "blue_percent": self.blue_percent,
            "green_percent": self.green_percent,
            "health_passed": self.health_passed,
            "health_summary": self.health_summary,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


def default_shift_progression() -> List[ShiftStep]:
    """The standard 10 -> 50 -> 100 progression."""
    return [
        ShiftStep(green_percent=10, dwell_seconds=2.0),
        ShiftStep(green_percent=50, dwell_seconds=2.0),
        ShiftStep(green_percent=100, dwell_seconds=2.0),
    ]


class TrafficShifter:
    """
    Drives the blue->green traffic shift, calling a hook on each percentage change
    so the caller can persist the split to DynamoDB.
    """

    def __init__(
        self,
        health_checker: HealthChecker,
        progression: List[ShiftStep] = None,
        on_shift: Callable[[int, int], Awaitable[None]] = None,
    ):
        self.health_checker = health_checker
        self.progression = progression or default_shift_progression()
        self.on_shift = on_shift  # async callable invoked after each step

    async def run(self) -> Dict[str, Any]:
        """
        Execute the full shift progression.
        Returns aggregate result + per-step details. Stops on first failure.
        """
        start = time.time()
        step_results: List[ShiftResult] = []
        final_split = {"blue": 100, "green": 0}
        all_passed = True
        halt_reason = ""

        for idx, step in enumerate(self.progression, start=1):
            blue_pct = 100 - step.green_percent
            green_pct = step.green_percent
            step_start = time.time()

            logger.info(
                f"[TrafficShifter] Step {idx}: shifting to blue={blue_pct}% / green={green_pct}%"
            )

            # Update persisted split BEFORE dwelling (dashboard sees the change)
            if self.on_shift:
                try:
                    await self.on_shift(blue_pct, green_pct)
                except Exception as e:
                    logger.error(f"[TrafficShifter] on_shift hook failed: {e}")

            # Dwell before health check (simulate traffic settling)
            await asyncio.sleep(step.dwell_seconds)

            # Run health checks against the (now-receiving-traffic) green slot
            health_summary = await self.health_checker.run_all()
            step_duration_ms = int((time.time() - step_start) * 1000)

            result = ShiftResult(
                step_number=idx,
                blue_percent=blue_pct,
                green_percent=green_pct,
                health_passed=health_summary["passed"],
                health_summary=health_summary,
                duration_ms=step_duration_ms,
            )

            if not health_summary["passed"]:
                result.error = (
                    f"{health_summary['checks_failed']} of "
                    f"{health_summary['checks_run']} checks failed"
                )
                logger.error(
                    f"[TrafficShifter] Step {idx} HALTED: {result.error}"
                )
                step_results.append(result)
                all_passed = False
                halt_reason = f"Health check failed at {green_pct}% green"
                final_split = {"blue": blue_pct, "green": green_pct}
                break

            logger.info(
                f"[TrafficShifter] Step {idx} OK in {step_duration_ms}ms — "
                f"{health_summary['checks_passed']}/{health_summary['checks_run']} checks passed"
            )
            step_results.append(result)
            final_split = {"blue": blue_pct, "green": green_pct}

        total_duration_ms = int((time.time() - start) * 1000)

        return {
            "status": "ok" if all_passed else "halted",
            "passed": all_passed,
            "halt_reason": halt_reason,
            "final_split": final_split,
            "steps_completed": len(step_results),
            "steps_total": len(self.progression),
            "total_duration_ms": total_duration_ms,
            "step_results": [r.to_dict() for r in step_results],
        }


async def monitoring_window(
    health_checker: HealthChecker,
    duration_seconds: int = 60,
    interval_seconds: int = 10,
) -> Dict[str, Any]:
    """
    After 100% green is reached, watch the slot for a fixed window.
    Runs HealthChecker every `interval_seconds`; fails on first failure.
    """
    start = time.time()
    checks_run = 0
    checks_passed = 0
    failures: List[Dict[str, Any]] = []

    logger.info(
        f"[Monitoring] Starting {duration_seconds}s observation window "
        f"(interval={interval_seconds}s)"
    )

    while (time.time() - start) < duration_seconds:
        result = await health_checker.run_all()
        checks_run += 1
        if result["passed"]:
            checks_passed += 1
        else:
            failures.append({
                "elapsed_seconds": int(time.time() - start),
                "summary": result,
            })
            logger.error(
                f"[Monitoring] Health degraded at "
                f"{int(time.time() - start)}s into window"
            )
            return {
                "status": "degraded",
                "passed": False,
                "duration_seconds": int(time.time() - start),
                "checks_run": checks_run,
                "checks_passed": checks_passed,
                "failures": failures,
            }
        await asyncio.sleep(interval_seconds)

    total_seconds = int(time.time() - start)
    logger.info(
        f"[Monitoring] Window complete — {checks_passed}/{checks_run} checks passed "
        f"over {total_seconds}s"
    )
    return {
        "status": "stable",
        "passed": True,
        "duration_seconds": total_seconds,
        "checks_run": checks_run,
        "checks_passed": checks_passed,
        "failures": [],
    }