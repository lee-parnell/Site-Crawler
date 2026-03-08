from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DelayConfig:
    min: float = 1.0
    max: float = 3.0


@dataclass
class RetryConfig:
    max_retries: int = 3
    backoff: float = 15.0


@dataclass
class FilterConfig:
    respect_robots: bool = True
    exclude_extensions: list = field(default_factory=lambda: [
        ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".zip", ".rar", ".css", ".js", ".json",
        ".mp4", ".mp3", ".avi", ".mov",
    ])
    exclude_patterns: list = field(default_factory=list)
    include_patterns: list = field(default_factory=list)


@dataclass
class BrowserConfig:
    headless: bool = True


@dataclass
class CrawlerConfig:
    start_url: str = "https://example.com"
    allowed_domain: str = "example.com"
    max_pages: Optional[int] = None
    delays: DelayConfig = field(default_factory=DelayConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    filters: FilterConfig = field(default_factory=FilterConfig)
    browser: BrowserConfig = field(default_factory=BrowserConfig)
    output_dir: str = "output/pages"
    state_file: str = "crawler_state.json"
    log_file: str = "crawler.log"


def load_config(config_path: str = "config.yaml") -> CrawlerConfig:
    """Load config from YAML file. Missing file returns defaults."""
    path = Path(config_path)
    if not path.exists():
        return CrawlerConfig()

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    cfg = CrawlerConfig()

    crawler_data = data.get("crawler", {})
    cfg.start_url = crawler_data.get("start_url", cfg.start_url)
    cfg.allowed_domain = crawler_data.get("allowed_domain", cfg.allowed_domain)
    cfg.max_pages = crawler_data.get("max_pages", cfg.max_pages)

    delay_data = data.get("delays", {})
    cfg.delays.min = delay_data.get("min", cfg.delays.min)
    cfg.delays.max = delay_data.get("max", cfg.delays.max)

    retry_data = data.get("retry", {})
    cfg.retry.max_retries = retry_data.get("max_retries", cfg.retry.max_retries)
    cfg.retry.backoff = retry_data.get("backoff", cfg.retry.backoff)

    filter_data = data.get("filters", {})
    cfg.filters.respect_robots = filter_data.get("respect_robots", cfg.filters.respect_robots)
    if "exclude_extensions" in filter_data:
        cfg.filters.exclude_extensions = filter_data["exclude_extensions"]
    cfg.filters.exclude_patterns = filter_data.get("exclude_patterns", cfg.filters.exclude_patterns)
    cfg.filters.include_patterns = filter_data.get("include_patterns", cfg.filters.include_patterns)

    cfg.browser.headless = data.get("browser", {}).get("headless", cfg.browser.headless)
    cfg.output_dir = data.get("output", {}).get("dir", cfg.output_dir)
    cfg.state_file = data.get("state_file", cfg.state_file)
    cfg.log_file = data.get("log_file", cfg.log_file)

    return cfg


def apply_cli_overrides(cfg: CrawlerConfig, args) -> CrawlerConfig:
    """Merge argparse values into config. CLI always wins over YAML."""
    if args.url is not None:
        cfg.start_url = args.url
    if args.domain is not None:
        cfg.allowed_domain = args.domain
    if args.max_pages is not None:
        cfg.max_pages = args.max_pages
    if args.min_delay is not None:
        cfg.delays.min = args.min_delay
    if args.max_delay is not None:
        cfg.delays.max = args.max_delay
    if args.headless is not None:
        cfg.browser.headless = args.headless
    if args.exclude:
        cfg.filters.exclude_patterns.extend(args.exclude)
    if args.ignore_robots:
        cfg.filters.respect_robots = False
    return cfg