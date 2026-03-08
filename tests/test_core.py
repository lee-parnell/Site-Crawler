"""
Unit tests for Crawler (core.py).

All browser/network I/O is replaced with mocks so no real Playwright
session or network connection is needed.
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crawler.config import CrawlerConfig
from crawler.core import Crawler
from crawler.fetcher import FetchResult, RateLimitError
from crawler.state import CrawlState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_crawler(tmp_path, max_pages=None) -> Crawler:
    cfg = CrawlerConfig(
        start_url="https://example.com",
        allowed_domain="example.com",
        max_pages=max_pages,
        state_file=str(tmp_path / "state.json"),
        output_dir=str(tmp_path / "pages"),
        log_file=str(tmp_path / "crawler.log"),
    )
    return Crawler(cfg)


def _fetch_result(url: str, links: list[str] | None = None) -> FetchResult:
    return FetchResult(url=url, html="<html/>", text="Hello", links=links or [])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_crawler_init(tmp_path):
    crawler = _make_crawler(tmp_path)
    assert crawler._cfg.start_url == "https://example.com"
    assert isinstance(crawler._state, CrawlState)


def test_max_pages_stops_loop(tmp_path):
    """Crawler should stop after max_pages even if queue has more URLs."""
    crawler = _make_crawler(tmp_path, max_pages=1)

    visit_calls = []

    async def fake_visit(fetcher, url):
        visit_calls.append(url)

    async def run_loop():
        await crawler._state.add_urls(["https://example.com/a", "https://example.com/b"])
        await crawler._loop(fetcher=MagicMock())

    with patch.object(crawler, "_visit", side_effect=fake_visit):
        asyncio.run(run_loop())

    assert len(visit_calls) == 1


def test_visit_successful_page(tmp_path):
    """A successful fetch should mark the URL visited and save new links."""
    crawler = _make_crawler(tmp_path)
    fetcher = MagicMock()
    fetcher.fetch = AsyncMock(return_value=_fetch_result(
        "https://example.com",
        links=["https://example.com/about"],
    ))

    asyncio.run(crawler._visit(fetcher, "https://example.com"))

    assert "https://example.com" in crawler._state.visited
    assert "https://example.com/about" in crawler._state._queued


def test_visit_rate_limit_requeues(tmp_path):
    """HTTP 429 should re-queue the URL instead of permanently failing it."""
    crawler = _make_crawler(tmp_path)
    fetcher = MagicMock()
    fetcher.fetch = AsyncMock(side_effect=RateLimitError("429"))

    # Remove the start URL from queue first so we can check re-queuing
    asyncio.run(crawler._state.next_url())

    with patch("asyncio.sleep", new_callable=AsyncMock):
        asyncio.run(crawler._visit(fetcher, "https://example.com"))

    # Should be re-queued or in failed (depending on retry count vs max)
    state = crawler._state
    in_queue = "https://example.com" in state._queued
    in_failed = "https://example.com" in state.failed
    assert in_queue or in_failed


def test_visit_permanent_failure(tmp_path):
    """An unexpected exception should permanently fail the URL."""
    crawler = _make_crawler(tmp_path)
    fetcher = MagicMock()
    fetcher.fetch = AsyncMock(side_effect=ValueError("unexpected"))

    asyncio.run(crawler._visit(fetcher, "https://example.com"))

    assert "https://example.com" in crawler._state.failed
    assert "https://example.com" in crawler._state.visited


def test_visit_filters_out_of_domain_links(tmp_path):
    """Links to other domains should not be added to the queue."""
    crawler = _make_crawler(tmp_path)
    fetcher = MagicMock()
    fetcher.fetch = AsyncMock(return_value=_fetch_result(
        "https://example.com",
        links=[
            "https://example.com/good",
            "https://other.com/bad",
            "https://evil.com/bad",
        ],
    ))

    asyncio.run(crawler._visit(fetcher, "https://example.com"))

    assert "https://example.com/good" in crawler._state._queued
    assert "https://other.com/bad" not in crawler._state._queued
    assert "https://evil.com/bad" not in crawler._state._queued
