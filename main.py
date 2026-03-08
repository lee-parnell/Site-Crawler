from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from crawler.config import load_config, apply_cli_overrides


def setup_logging(log_file: str) -> None:
    root = logging.getLogger("crawler")
    root.setLevel(logging.DEBUG)
    if root.handlers:
        return

    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    root.addHandler(fh)
    root.addHandler(ch)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="site-crawler",
        description="Async BFS web crawler — archives pages as Markdown files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python main.py                                         # use config.yaml defaults
  python main.py --url https://example.com --domain example.com
  python main.py --max-pages 50 --headless false
  python main.py --exclude "/login/" "/admin/"
  python main.py --reset                                 # clear state and restart
        """,
    )

    parser.add_argument(
        "--config", default="config.yaml", metavar="FILE",
        help="YAML config file (default: config.yaml)"
    )
    parser.add_argument(
        "--url", default=None, metavar="URL",
        help="Override start URL"
    )
    parser.add_argument(
        "--domain", default=None, metavar="DOMAIN",
        help="Override allowed domain"
    )
    parser.add_argument(
        "--max-pages", type=int, default=None, metavar="N",
        help="Stop after crawling N pages"
    )
    parser.add_argument(
        "--min-delay", type=float, default=None, metavar="S",
        help="Override minimum delay between requests (seconds)"
    )
    parser.add_argument(
        "--max-delay", type=float, default=None, metavar="S",
        help="Override maximum delay between requests (seconds)"
    )
    parser.add_argument(
        "--headless", type=lambda v: v.lower() != "false", default=None,
        metavar="BOOL",
        help="Headless browser: true (default) or false to show window"
    )
    parser.add_argument(
        "--exclude", nargs="+", default=[], metavar="PATTERN",
        help="Additional URL exclude patterns (regex), e.g. /login/ /admin/"
    )
    parser.add_argument(
        "--ignore-robots", action="store_true",
        help="Ignore robots.txt restrictions"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete saved state file and restart crawl from scratch"
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cfg = load_config(args.config)
    cfg = apply_cli_overrides(cfg, args)

    if args.reset and os.path.exists(cfg.state_file):
        os.remove(cfg.state_file)
        print(f"State cleared — starting fresh.")

    setup_logging(cfg.log_file)
    os.makedirs(cfg.output_dir, exist_ok=True)

    from crawler.core import Crawler
    asyncio.run(Crawler(cfg).run())


if __name__ == "__main__":
    main()