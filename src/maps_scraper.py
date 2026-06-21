"""
Google Maps scraper using Playwright.
Two-pass approach: collect place URLs from sidebar, then visit each for details.
"""

import random
import re
import time
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class GoogleMapsScraper:
    def __init__(
        self,
        headless: bool = False,
        delay_between_results: float = 2,
        delay_between_scrolls: float = 3,
    ):
        self.headless = headless
        self.delay_results = delay_between_results
        self.delay_scrolls = delay_between_scrolls

    # ── Public ────────────────────────────────────────────────────

    def search(
        self,
        keyword: str,
        location: str,
        max_results: int = 50,
        on_result=None,
    ) -> list:
        """
        Search Google Maps and return list of business dicts.
        on_result: optional callback(business_dict) called for each result.
        """
        results = []
        query = f"{keyword} {location}"

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            ctx = browser.new_context(
                user_agent=_UA,
                viewport={"width": 1280, "height": 900},
                locale="en-US",
            )
            ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )
            page = ctx.new_page()

            try:
                self._open_search(page, query)
                place_urls = self._collect_urls(page, max_results)
                print(f"  [→] {len(place_urls)} listings found, extracting details...")

                for i, url in enumerate(place_urls, 1):
                    biz = self._extract(page, url)
                    if biz:
                        biz["keyword"] = keyword
                        biz["search_location"] = location
                        results.append(biz)
                        print(f"  [+] {i}/{len(place_urls)}  {biz.get('name', '?')}")
                        if on_result:
                            on_result(biz)
                    self._jitter(self.delay_results)

            except Exception as exc:
                print(f"  [!] Scraper error: {exc}")
            finally:
                browser.close()

        return results

    # ── Internal ──────────────────────────────────────────────────

    def _open_search(self, page, query: str):
        url = f"https://www.google.com/maps/search/{quote_plus(query)}"
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        self._jitter(2)

        for label in ("Accept all", "Accept", "Reject all"):
            try:
                btn = page.locator(f'button:has-text("{label}")').first
                if btn.is_visible(timeout=2_000):
                    btn.click()
                    self._jitter(1)
                    break
            except PlaywrightTimeout:
                pass

        try:
            page.wait_for_selector('[role="feed"]', timeout=15_000)
        except PlaywrightTimeout:
            raise RuntimeError(f"Maps results did not load for: {query}")

    def _collect_urls(self, page, max_results: int) -> list:
        """Scroll the results panel and harvest /maps/place/ links."""
        seen: dict = {}
        no_new = 0
        feed = page.locator('[role="feed"]')

        for _ in range(40):
            links = page.locator('a[href*="/maps/place/"]').all()
            prev = len(seen)
            for lnk in links:
                try:
                    href = lnk.get_attribute("href") or ""
                    if "/maps/place/" in href:
                        clean = re.split(r"[?#]", href)[0]
                        seen[clean] = True
                except Exception:
                    pass

            if len(seen) >= max_results:
                break

            no_new = 0 if len(seen) > prev else no_new + 1
            if no_new >= 4:
                break

            try:
                if page.locator("text=You've reached the end").is_visible(timeout=500):
                    break
            except Exception:
                pass

            try:
                feed.evaluate("el => el.scrollBy(0, 1500)")
            except Exception:
                pass
            self._jitter(self.delay_scrolls)

        return list(seen.keys())[:max_results]

    def _extract(self, page, url: str) -> dict | None:
        """Navigate to a place page and pull structured fields."""
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_selector("h1", timeout=10_000)
            self._jitter(1)
        except Exception:
            return None

        biz: dict = {"maps_url": page.url, "email": "", "owner_name": ""}
        biz["name"]     = self._text(page, "h1")
        biz["address"]  = self._aria(page, '[data-item-id="address"]',        "Address: ")
        biz["phone"]    = self._aria(page, '[data-item-id^="phone:tel:"]',    "Phone: ")
        biz["category"] = self._text(page, "button[jsaction*='category']")

        website = self._href(page, '[data-item-id="authority"]')
        biz["website"] = website
        biz["domain"]  = self._domain(website)

        return biz if biz.get("name") else None

    # ── Helpers ───────────────────────────────────────────────────

    def _text(self, page, sel: str) -> str:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2_000):
                return (el.text_content(timeout=2_000) or "").strip()
        except Exception:
            pass
        return ""

    def _aria(self, page, sel: str, strip: str = "") -> str:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2_000):
                return (el.get_attribute("aria-label") or "").replace(strip, "").strip()
        except Exception:
            pass
        return ""

    def _href(self, page, sel: str) -> str:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2_000):
                return el.get_attribute("href") or ""
        except Exception:
            pass
        return ""

    @staticmethod
    def _domain(url: str) -> str:
        m = re.search(r"https?://(?:www\.)?([^/\s?#]+)", url)
        return m.group(1) if m else ""

    def _jitter(self, base: float):
        time.sleep(base * random.uniform(0.7, 1.4))
