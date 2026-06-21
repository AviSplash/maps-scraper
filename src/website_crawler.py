"""
Crawl business websites to extract email addresses and page text
for downstream n8n / AI owner-name enrichment.
"""

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_CONTACT_PATHS = [
    "/contact", "/contact-us", "/contactus", "/contact_us",
    "/about",   "/about-us",   "/aboutus",   "/about_us",
    "/team",    "/our-team",   "/staff",     "/people",
    "/reach-us", "/get-in-touch",
]

_JUNK_DOMAINS = frozenset({
    "example.com", "sentry.io", "wix.com", "squarespace.com",
    "wordpress.com", "godaddy.com", "google.com", "facebook.com",
    "schema.org", "w3.org", "jquery.com", "cloudflare.com",
    "amazonaws.com", "instagram.com", "twitter.com", "yelp.com",
})

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


class WebsiteCrawler:
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self._sess = requests.Session()
        self._sess.headers.update(_HEADERS)

    def crawl(self, website_url: str) -> dict:
        """
        Returns:
            emails       – list of email strings (deduplicated, filtered)
            page_text    – visible text up to 5 000 chars  (for AI enrichment)
            pages_crawled – URLs that were actually fetched
        """
        if not website_url:
            return {"emails": [], "page_text": "", "pages_crawled": []}

        base = _normalise(website_url)
        if not base:
            return {"emails": [], "page_text": "", "pages_crawled": []}

        emails: set = set()
        texts:  list = []
        visited: list = []

        r = self._fetch(base)
        if r:
            emails.update(r["emails"])
            texts.append(r["text"])
            visited.append(base)

        for path in _CONTACT_PATHS:
            if emails and len(visited) >= 3:
                break
            url = urljoin(base, path)
            if url in visited:
                continue
            r = self._fetch(url)
            if r:
                emails.update(r["emails"])
                texts.append(r["text"])
                visited.append(url)

        biz_domain = _domain(base)
        clean = _filter(emails, biz_domain)

        return {
            "emails": list(clean),
            "page_text": "\n\n".join(texts)[:5_000],
            "pages_crawled": visited,
        }

    def _fetch(self, url: str) -> dict | None:
        try:
            resp = self._sess.get(url, timeout=self.timeout, allow_redirects=True)
            if resp.status_code != 200:
                return None
            if "text/html" not in resp.headers.get("content-type", ""):
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style", "noscript", "svg", "footer", "nav"]):
                tag.decompose()

            text  = soup.get_text(separator=" ", strip=True)[:2_000]
            found = set(_EMAIL_RE.findall(resp.text))
            return {"emails": found, "text": text}
        except Exception:
            return None


def _normalise(url: str) -> str:
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def _filter(emails: set, biz_domain: str) -> set:
    clean: set = set()
    for em in emails:
        em = em.lower().strip()
        dom = em.split("@")[-1]
        if dom in _JUNK_DOMAINS:
            continue
        if any(j in dom for j in ("example", "test", "placeholder", "noreply", "no-reply")):
            continue
        clean.add(em)
    return clean
