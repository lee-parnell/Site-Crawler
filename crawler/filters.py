from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


class UrlFilter:
    """
    Generic URL filter. Decisions are based on:
      1. Domain allowlist (www-normalised)
      2. Extension blocklist
      3. Exclude regex patterns  (any match → blocked)
      4. Include regex patterns  (if non-empty, URL must match at least one)
      5. robots.txt (optional)
    """

    def __init__(
        self,
        allowed_domain: str,
        exclude_extensions: list[str],
        exclude_patterns: list[str],
        include_patterns: list[str],
        respect_robots: bool = True,
    ) -> None:
        self._allowed_domain = self._normalize_domain(allowed_domain)
        self._exclude_ext = [e.lower() for e in exclude_extensions]
        self._exclude_re = [re.compile(p) for p in exclude_patterns]
        self._include_re = [re.compile(p) for p in include_patterns]
        self._respect_robots = respect_robots
        self._robots_cache: dict[str, Optional[RobotFileParser]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, url: str) -> tuple[bool, str]:
        """Return (allowed, reason_string)."""
        if not url or not url.startswith(("http://", "https://")):
            return False, "invalid"

        parsed = urlparse(url)

        if self._normalize_domain(parsed.netloc) != self._allowed_domain:
            return False, "domain"

        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in self._exclude_ext):
            return False, "extension"

        # Use path + query for pattern matching
        target = parsed.path + ("?" + parsed.query if parsed.query else "")

        if any(r.search(target) for r in self._exclude_re):
            return False, "excluded"

        if self._include_re and not any(r.search(target) for r in self._include_re):
            return False, "not_included"

        if self._respect_robots and not self._robots_allowed(url, parsed):
            return False, "robots"

        return True, "allowed"

    def allow(self, url: str) -> bool:
        ok, _ = self.check(url)
        return ok

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _robots_allowed(self, url: str, parsed) -> bool:
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots_cache:
            rp = RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                rp.read()
                self._robots_cache[base] = rp
            except Exception:
                self._robots_cache[base] = None
        rp = self._robots_cache[base]
        return rp.can_fetch("*", url) if rp else True

    @staticmethod
    def _normalize_domain(netloc: str) -> str:
        host = (netloc or "").split(":", 1)[0].lower()
        return host[4:] if host.startswith("www.") else host