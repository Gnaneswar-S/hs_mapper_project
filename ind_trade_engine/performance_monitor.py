# performance_monitor.py
# Lightweight performance monitoring — tracks API call durations and slow queries.
# All data stays in-memory; nothing is written to the DB by default.

import time
import logging
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger("performance_monitor")

# In-memory store: {operation_name: [duration_seconds, ...]}
_TIMINGS: dict[str, list] = defaultdict(list)
_MAX_SAMPLES = 100   # keep last N samples per operation


class Timer:
    """Context manager for timing a code block."""

    def __init__(self, operation: str):
        self.operation = operation
        self._start    = 0.0

    def __enter__(self):
        self._start = time.monotonic()
        return self

    def __exit__(self, *args):
        duration = time.monotonic() - self._start
        record_timing(self.operation, duration)


def record_timing(operation: str, duration_seconds: float) -> None:
    """Record a single timing sample for an operation."""
    samples = _TIMINGS[operation]
    samples.append(duration_seconds)
    if len(samples) > _MAX_SAMPLES:
        samples.pop(0)
    if duration_seconds > 10:
        logger.warning(f"Slow operation '{operation}': {duration_seconds:.1f}s")


def get_stats(operation: str) -> dict:
    """Return mean, min, max, count for an operation."""
    samples = _TIMINGS.get(operation, [])
    if not samples:
        return {"operation": operation, "count": 0}
    return {
        "operation": operation,
        "count":     len(samples),
        "mean_s":    round(sum(samples) / len(samples), 3),
        "min_s":     round(min(samples), 3),
        "max_s":     round(max(samples), 3),
    }


def get_all_stats() -> list[dict]:
    """Return stats for all tracked operations."""
    return [get_stats(op) for op in sorted(_TIMINGS.keys())]


def reset() -> None:
    """Clear all recorded timings."""
    _TIMINGS.clear()