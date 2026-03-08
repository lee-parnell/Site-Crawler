from __future__ import annotations

import logging
from dataclasses import dataclass

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

logger = logging.getLogger("crawler")


class RateLimitError(Exception):
    """Raised when the server responds with HTTP 429 Too Many Requests."""


@dataclass
class FetchResult:
    url: str
    html: str
    text: str
    links: list[str]


class PageFetcher:
    """Loads a page with Playwright and extracts content."""

    def __init__(self, page: Page) -> None:
        self._page = page

    async def fetch(self, url: str) -> FetchResult:
        response = await self._page.goto(url, wait_until="domcontentloaded", timeout=90_000)

        # Wait for network to settle; continue even if it times out
        try:
            await self._page.wait_for_load_state("networkidle", timeout=15_000)
        except PlaywrightTimeout:
            pass

        await self._page.wait_for_timeout(1_000)

        if response and response.status == 429:
            raise RateLimitError(f"Rate limited: {url}")

        html = await self._page.content()
        text = await self._page.inner_text("body")
        links = await self._page.locator("a[href]").evaluate_all(
            "els => els.map(e => e.href).filter(Boolean)"
        )

        return FetchResult(url=url, html=html, text=text, links=links)