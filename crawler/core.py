from __future__ import annotations

import asyncio
import logging
import random
import signal
from collections import Counter

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

from .config import CrawlerConfig
from .exporter import MarkdownExporter
from .fetcher import PageFetcher, RateLimitError
from .filters import UrlFilter
from .state import CrawlState

logger = logging.getLogger("crawler")


class Crawler:
    """
    Async BFS crawler.

    Reads configuration from CrawlerConfig, persists state to JSON after
    every page, and writes each page as a Markdown file.
    """

    def __init__(self, cfg: CrawlerConfig) -> None:
        self._cfg = cfg
        self._state = CrawlState(cfg.state_file, cfg.start_url)
        self._filter = UrlFilter(
            allowed_domain=cfg.allowed_domain,
            exclude_extensions=cfg.filters.exclude_extensions,
            exclude_patterns=cfg.filters.exclude_patterns,
            include_patterns=cfg.filters.include_patterns,
            respect_robots=cfg.filters.respect_robots,
        )
        self._exporter = MarkdownExporter(cfg.output_dir)
        self._stop = False

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        self._setup_signal_handler()
        logger.info(f"Starting crawl — {self._state.stats}")

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self._cfg.browser.headless)
            context = await browser.new_context()
            page = await context.new_page()
            fetcher = PageFetcher(page)
            try:
                await self._loop(fetcher)
            finally:
                await context.close()
                await browser.close()

        self._state.save()
        logger.info(f"Crawl complete — {self._state.stats}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _loop(self, fetcher: PageFetcher) -> None:
        pages_done = 0

        while not self._stop:
            if self._cfg.max_pages and pages_done >= self._cfg.max_pages:
                logger.info(f"Reached max_pages limit ({self._cfg.max_pages})")
                break

            url = await self._state.next_url()
            if url is None:
                logger.info("Queue empty — crawl finished")
                break

            await self._visit(fetcher, url)
            pages_done += 1

    async def _visit(self, fetcher: PageFetcher, url: str) -> None:
        retry_count = self._state.retry_count(url)

        if retry_count > 0:
            backoff = self._cfg.retry.backoff * (2 ** (retry_count - 1))
            logger.info(f"Retry {retry_count} for {url} — waiting {backoff:.0f}s")
            await asyncio.sleep(backoff)
        else:
            delay = random.uniform(self._cfg.delays.min, self._cfg.delays.max)
            logger.info(f"Visiting: {url}  (delay {delay:.1f}s)")
            await asyncio.sleep(delay)

        try:
            result = await fetcher.fetch(url)
            self._exporter.write(url, result.text)

            reason_counter = Counter()
            new_urls = []
            for link in result.links:
                ok, reason = self._filter.check(link)
                reason_counter[reason] += 1
                if ok:
                    new_urls.append(link)

            logger.info(
                f"Links: total={len(result.links)} allowed={len(new_urls)} "
                f"reasons={dict(reason_counter)}"
            )

            await self._state.add_urls(new_urls)
            await self._state.mark_visited(url)
            self._state.save()
            logger.info(f"Done: {url}  (queued={len(self._state.queue)})")

        except RateLimitError:
            backoff = self._cfg.retry.backoff * 4
            logger.warning(f"Rate limited: {url} — sleeping {backoff:.0f}s then re-queuing")
            await asyncio.sleep(backoff)
            await self._state.mark_failed(url, self._cfg.retry.max_retries)
            self._state.save()

        except PlaywrightTimeout:
            logger.warning(f"Timeout (will retry): {url}")
            await self._state.mark_failed(url, self._cfg.retry.max_retries)
            self._state.save()

        except Exception as e:
            logger.error(f"Permanent failure: {url} — {e}")
            await self._state.mark_failed_permanent(url)
            self._state.save()

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _setup_signal_handler(self) -> None:
        def handle(sig, frame):
            logger.info("Interrupted — saving state and shutting down...")
            self._stop = True
            self._state.save()
            logger.info(f"State saved. {self._state.stats}")

        signal.signal(signal.SIGINT, handle)