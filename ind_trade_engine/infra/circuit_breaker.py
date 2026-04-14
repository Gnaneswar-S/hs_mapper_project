# circuit_breaker.py
# Simple circuit breaker to prevent cascading failures when the NVIDIA API is down.
#
# States: CLOSED (normal) → OPEN (failing, block calls) → HALF_OPEN (probe recovery)
#
# Usage:
#   breaker = CircuitBreaker("nvidia_api", failure_threshold=5, recovery_timeout=60)
#   if breaker.allow_request():
#       try:
#           result = call_api()
#           breaker.record_success()
#       except Exception:
#           breaker.record_failure()

import time
import logging
from enum import Enum

logger = logging.getLogger("circuit_breaker")


class State(Enum):
    CLOSED    = "closed"      # Normal — requests pass through
    OPEN      = "open"        # Failing — requests blocked
    HALF_OPEN = "half_open"   # Probing — one request allowed through


class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max: int = 1,
    ):
        self.name              = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout  = recovery_timeout
        self.half_open_max     = half_open_max

        self._state         = State.CLOSED
        self._failure_count = 0
        self._last_failure  = 0.0
        self._half_open_calls = 0

    @property
    def state(self) -> State:
        if self._state == State.OPEN:
            if time.monotonic() - self._last_failure > self.recovery_timeout:
                self._state = State.HALF_OPEN
                self._half_open_calls = 0
                logger.info(f"Circuit '{self.name}' → HALF_OPEN")
        return self._state

    def allow_request(self) -> bool:
        s = self.state
        if s == State.CLOSED:
            return True
        if s == State.HALF_OPEN and self._half_open_calls < self.half_open_max:
            self._half_open_calls += 1
            return True
        if s == State.OPEN:
            logger.warning(f"Circuit '{self.name}' is OPEN — request blocked")
        return False

    def record_success(self) -> None:
        self._failure_count = 0
        if self._state != State.CLOSED:
            logger.info(f"Circuit '{self.name}' → CLOSED")
        self._state = State.CLOSED

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure = time.monotonic()
        if self._state == State.HALF_OPEN or self._failure_count >= self.failure_threshold:
            self._state = State.OPEN
            logger.error(f"Circuit '{self.name}' → OPEN after {self._failure_count} failures")

    def get_status(self) -> dict:
        return {
            "name":           self.name,
            "state":          self.state.value,
            "failure_count":  self._failure_count,
            "threshold":      self.failure_threshold,
        }


# Shared instance for NVIDIA API — import and use in nvidia_service.py
nvidia_breaker = CircuitBreaker("nvidia_api", failure_threshold=5, recovery_timeout=120)