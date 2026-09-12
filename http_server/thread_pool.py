"""
Thread pool worker management for offloading blocking tasks.
"""

from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any, Optional


class WorkerPool:
    """Manages worker threads for executing blocking handlers and disk I/O."""
    def __init__(self, max_workers: int = 16):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="HTTPWorker"
        )
        self._is_shutdown = False

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """Submits a callable to the worker pool."""
        if self._is_shutdown:
            raise RuntimeError("Cannot submit task to shutdown WorkerPool")
        return self._executor.submit(fn, *args, **kwargs)

    def shutdown(self, wait: bool = True):
        """Shuts down the worker pool gracefully."""
        self._is_shutdown = True
        self._executor.shutdown(wait=wait)
