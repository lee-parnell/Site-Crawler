import asyncio
import pytest
from crawler.state import CrawlState


@pytest.fixture
def state(tmp_path):
    return CrawlState(str(tmp_path / "state.json"), "https://example.com")


def test_initial_queue_contains_start_url(state):
    assert "https://example.com" in state._queued


def test_next_url_returns_start_url(state):
    url = asyncio.run(state.next_url())
    assert url == "https://example.com"


def test_next_url_returns_none_when_empty(state):
    asyncio.run(state.next_url())  # consume the only URL
    url = asyncio.run(state.next_url())
    assert url is None


def test_add_urls_enqueues_new_entries(state):
    asyncio.run(state.add_urls(["https://example.com/a", "https://example.com/b"]))
    assert "https://example.com/a" in state._queued
    assert "https://example.com/b" in state._queued


def test_visited_url_not_re_queued(state):
    asyncio.run(state.mark_visited("https://example.com/page"))
    asyncio.run(state.add_urls(["https://example.com/page"]))
    assert "https://example.com/page" not in state._queued


def test_mark_failed_requeues_until_max(tmp_path):
    s = CrawlState(str(tmp_path / "s.json"), "https://example.com/x")
    asyncio.run(s.next_url())  # dequeue
    asyncio.run(s.mark_failed("https://example.com/x", max_retries=2))
    assert "https://example.com/x" in s._queued   # re-queued (count=1, max=2)
    asyncio.run(s.next_url())
    asyncio.run(s.mark_failed("https://example.com/x", max_retries=2))
    assert "https://example.com/x" in s.failed    # permanently failed (count=2)


def test_save_and_reload(state, tmp_path):
    asyncio.run(state.next_url())
    asyncio.run(state.mark_visited("https://example.com"))
    asyncio.run(state.add_urls(["https://example.com/page"]))
    state.save()

    reloaded = CrawlState(str(tmp_path / "state.json"), "https://example.com")
    assert "https://example.com" in reloaded.visited
    assert "https://example.com/page" in reloaded._queued


def test_stats_keys(state):
    s = state.stats
    assert "visited" in s and "failed" in s and "queued" in s
