"""
graceful_shutdown.py
════════════════════════════════════════════════════════════════════
Graceful shutdown handlers for clean application termination.
Ensures in-flight operations complete and data is flushed.
════════════════════════════════════════════════════════════════════
"""

import signal
import atexit
import logging
import threading
from typing import Callable, List

logger = logging.getLogger("graceful_shutdown")

# Registered cleanup callbacks
_CLEANUP_CALLBACKS: List[Callable] = []
_SHUTDOWN_LOCK = threading.Lock()
_IS_SHUTTING_DOWN = False


def register_cleanup(callback: Callable, name: str = None):
    """
    Register a cleanup function to run on shutdown.
    
    Args:
        callback: Function to call (should accept no args)
        name: Optional name for logging
    """
    _CLEANUP_CALLBACKS.append((callback, name or callback.__name__))
    logger.debug(f"Registered cleanup: {name or callback.__name__}")


def perform_shutdown():
    """Execute all registered cleanup functions"""
    global _IS_SHUTTING_DOWN

    with _SHUTDOWN_LOCK:
        if _IS_SHUTTING_DOWN:
            return
        _IS_SHUTTING_DOWN = True

    logger.info("🔌 Starting graceful shutdown...")

    for callback, name in _CLEANUP_CALLBACKS:
        try:
            logger.info(f"Running cleanup: {name}")
            callback()
            logger.debug(f"✓ Cleanup complete: {name}")
        except Exception as e:
            logger.error(f"Error during cleanup '{name}': {type(e).__name__}: {e}")

    logger.info("✓ Graceful shutdown complete")


def _handle_sigterm(signum, frame):
    """Handle SIGTERM signal"""
    logger.warning(f"Received signal {signum}, initiating graceful shutdown...")
    perform_shutdown()
    exit(0)


def _handle_sigint(signum, frame):
    """Handle SIGINT (Ctrl+C)"""
    logger.warning("Received SIGINT, initiating graceful shutdown...")
    perform_shutdown()
    exit(0)


def setup_shutdown_handlers():
    """
    Setup signal handlers and atexit hook for graceful shutdown.
    Call this once at app startup.
    """
    # Handle termination signals
    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigint)

    # Handle normal exit
    atexit.register(perform_shutdown)

    logger.info("Graceful shutdown handlers registered")


# Predefined cleanup callbacks

def flush_pending_queries():
    """Flush any pending query consumption to database"""
    logger.info("Flushing pending queries...")
    # This would be called to ensure rate limit updates are persisted


def flush_session_state():
    """Save session state before exit"""
    logger.info("Flushing session state...")
    # This would save active user sessions


def close_database_connections():
    """Close any open database connections"""
    logger.info("Closing database connections...")
    # This would close Supabase connections gracefully


def stop_background_tasks():
    """Stop any background tasks or threads"""
    logger.info("Stopping background tasks...")
    # This would stop monitoring tasks, cache cleanup, etc.
