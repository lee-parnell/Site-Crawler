from __future__ import annotations

import asyncio
import json
from collections import deque
from pathlib import Path
from typing import Optional


class CrawlState:
    """
    Thread-safe (asyncio-safe) BFS state with JSON persistence.

    Tracks visited URLs, failed URLs, retry counts, and the pending queue.
    Call save() after each page to support resuming from interruption.
    """

    def __init__(self, state_file: str, start_url: str) -> None:
        self._path = Path(state_file)
        self._start_url = start_url
        self._lock = asyncio.Lock()

        self.visited: set[str] = set()
        self.failed: set[str] = set()
        self.queue: deque[str] = deque()
        self._queued: set[str] = set()   # mirror of queue for O(1) duplicate check
        self._retry_counts: dict[str, int] = {}

        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            self._enqueue(self._start_url)
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self.visited = set(data.get("visited", []))
            self.failed = set(data.get("failed", []))
            self._retry_counts = data.get("retry_counts", {})
            for url in data.get("queue", []):
                self._enqueue(url)
            if not self.queue and not self.visited:
                self._enqueue(self._start_url)
        except Exception:
            self._enqueue(self._start_url)

    def save(self) -> None:
        self._path.write_text(
            json.dumps({
                "visited": list(self.visited),
                "failed": list(self.failed),
                "queue": list(self.queue),
                "retry_counts": self._retry_counts,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Queue operations (async-safe)
    # ------------------------------------------------------------------

    def _enqueue(self, url: str) -> None:
        """Internal: enqueue without lock (caller must hold lock or be in init)."""
        if url not in self._queued and url not in self.visited:
            self.queue.append(url)
            self._queued.add(url)

    async def next_url(self) -> Optional[str]:
        async with self._lock:
            while self.queue:
                url = self.queue.popleft()
                self._queued.discard(url)
                if url not in self.visited:
                    return url
            return None

    async def add_urls(self, urls: list[str]) -> None:
        async with self._lock:
            for url in urls:
                self._enqueue(url)

    # ------------------------------------------------------------------
    # Status updates
    # ------------------------------------------------------------------

    async def mark_visited(self, url: str) -> None:
        async with self._lock:
            self.visited.add(url)

    async def mark_failed(self, url: str, max_retries: int) -> None:
        """Increment retry count. Re-queue if under max_retries, else permanently fail."""
        async with self._lock:
            count = self._retry_counts.get(url, 0) + 1
            self._retry_counts[url] = count
            if count >= max_retries:
                self.failed.add(url)
                self.visited.add(url)
            else:
                self._enqueue(url)

    async def mark_failed_permanent(self, url: str) -> None:
        """Fail a URL immediately without counting toward retries (e.g. code errors)."""
        async with self._lock:
            self.failed.add(url)
            self.visited.add(url)

    def retry_count(self, url: str) -> int:
        return self._retry_counts.get(url, 0)

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        return {
            "visited": len(self.visited),
            "failed": len(self.failed),
            "queued": len(self.queue),
        }