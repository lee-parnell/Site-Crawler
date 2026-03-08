from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger("crawler")


def _safe_filename(url: str) -> str:
    """Derive a filesystem-safe .md filename from a URL."""
    parsed = urlparse(url)
    slug = parsed.path.strip("/").replace("/", "_") or "index"
    digest = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{slug}_{digest}.md"


class MarkdownExporter:
    """Writes page text content to Markdown files."""

    def __init__(self, output_dir: str) -> None:
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def write(self, url: str, text: str) -> Path:
        path = self._dir / _safe_filename(url)
        path.write_text(f"# {url}\n\n{text}", encoding="utf-8")
        logger.debug(f"Saved: {path.name}")
        return path