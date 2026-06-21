#!/usr/bin/env python3
"""
Google Maps Lead Scraper — CLI entry point
Usage:  python src/main.py [options]
        .\\run.ps1 [options]          (Windows shortcut)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml
from colorama import Fore, Style, init

from exporter import Exporter
from maps_scraper import GoogleMapsScraper
from n8n_client import N8nClient
from website_crawler import WebsiteCrawler

init(autoreset=True)


def _cfg(path: str) -> dict:
    p = Path(path)
    if p.exists():
        with open(p) as f:
            return yaml.safe_load(f) or {}
    return {}


def _args(cfg: dict) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Google Maps Lead Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python src/main.py --keyword "HVAC contractors" --location "Houston TX" --max 50
  python src/main.py --keyword "plumbers" --location "Dallas TX" --format csv
  python src/main.py              # uses keywords/location from config.yaml
        """,
    )
    p.add_argument("--keyword",  "-k", help="Search keyword")
    p.add_argument("--location", "-l", help="Target city/state")
    p.add_argument("--max",      "-m", type=int,
                   default=cfg.get("max_results", 50),
                   help="Max results per keyword (default %(default)s)")
    p.add_argument("--format",   "-f", nargs="+",
                   choices=["csv", "excel", "json"],
                   default=cfg.get("formats", ["csv", "excel", "json"]),
                   help="Output formats")
    p.add_argument("--output",   "-o",
                   default=cfg.get("output_dir", "./output"),
                   help="Output directory (default %(default)s)")
    p.add_argument("--headless", action="store_true",
                   default=cfg.get("headless", False),
                   help="Run browser hidden")
    p.add_argument("--no-crawl", action="store_true",
                   help="Skip website crawling (faster, no emails)")
    p.add_argument("--no-n8n",   action="store_true",
                   help="Skip n8n enrichment")
    p.add_argument("--config",   default="config.yaml",
                   help="Config file path (default %(default)s)")
    return p.parse_args()


def _run_one(keyword, location, args, cfg, scraper, crawler, n8n, exporter):
    print(f"\n{Fore.CYAN}{'─'*55}")
    print(f"  Keyword  : {keyword}")
    print(f"  Location : {location}")
    print(f"  Max      : {args.max}")
    print(f"{'─'*55}{Style.RESET_ALL}")

    print(f"{Fore.YELLOW}[1/3] Scraping Google Maps...{Style.RESET_ALL}")
    results = scraper.search(keyword, location, max_results=args.max)
    print(f"{Fore.GREEN}      Found {len(results)} businesses{Style.RESET_ALL}")
    if not results:
        return []

    n8n_cfg = cfg.get("n8n", {})
    use_n8n = (
        not args.no_n8n
        and n8n_cfg.get("enabled")
        and n8n_cfg.get("webhook_url")
    )

    if not args.no_crawl:
        print(f"{Fore.YELLOW}[2/3] Crawling websites for emails...{Style.RESET_ALL}")
    if use_n8n:
        print(f"{Fore.YELLOW}      + n8n AI enrichment for owner names{Style.RESET_ALL}")

    for i, biz in enumerate(results, 1):
        website   = biz.get("website", "")
        page_text = ""

        if not args.no_crawl and website:
            crawl = crawler.crawl(website)
            biz["email"] = "; ".join(crawl.get("emails", []))
            page_text    = crawl.get("page_text", "")

        if use_n8n:
            enriched = n8n.enrich(biz, page_text)
            biz["owner_name"] = enriched.get("owner_name", "")

        pct = int(i / len(results) * 100)
        print(f"\r      {pct}% ({i}/{len(results)})   ", end="", flush=True)

    print()

    print(f"{Fore.YELLOW}[3/3] Exporting...{Style.RESET_ALL}")
    exporter.export(results, keyword, location)
    return results


def main():
    cfg  = _cfg("config.yaml")
    args = _args(cfg)

    if args.keyword:
        searches = [(args.keyword, args.location or cfg.get("location", ""))]
    else:
        kws = cfg.get("keywords", [])
        loc = args.location or cfg.get("location", "")
        if not kws:
            print(f"{Fore.RED}[X] No keywords. Use --keyword or set keywords in config.yaml{Style.RESET_ALL}")
            sys.exit(1)
        searches = [(kw, loc) for kw in kws]

    sc_cfg   = cfg.get("scraper", {})
    scraper  = GoogleMapsScraper(
        headless=args.headless,
        delay_between_results=sc_cfg.get("delay_between_results", 2),
        delay_between_scrolls=sc_cfg.get("delay_between_scrolls", 3),
    )
    crawler  = WebsiteCrawler(timeout=cfg.get("crawl_timeout", 10))
    n8n_cfg  = cfg.get("n8n", {})
    n8n      = N8nClient(
        webhook_url=n8n_cfg.get("webhook_url", ""),
        timeout=n8n_cfg.get("timeout", 30),
    )
    exporter = Exporter(output_dir=args.output, formats=args.format)

    print(f"\n{Fore.MAGENTA}{'═'*55}")
    print(f"   Google Maps Lead Scraper  |  {len(searches)} search(es)")
    print(f"{'═'*55}{Style.RESET_ALL}")

    total = []
    for kw, loc in searches:
        total.extend(_run_one(kw, loc, args, cfg, scraper, crawler, n8n, exporter))

    print(f"\n{Fore.GREEN}{'═'*55}")
    print(f"   Done — {len(total)} total leads collected")
    print(f"   Saved to: {args.output}")
    print(f"{'═'*55}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
