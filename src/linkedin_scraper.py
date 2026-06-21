"""
LinkedIn owner-lookup via Google site-search.

Strategy: query Google for `site:linkedin.com/in <biz_name> <location>`
with owner-title keywords, parse organic results, then score each
candidate against the known business signals before accepting a match.

No LinkedIn credentials or API required — purely public search.
"""

import re
import time
import random
from urllib.parse import quote_plus, urlparse

import requests
from bs4 import BeautifulSoup


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

_OWNER_TITLES = re.compile(
    r"\b(owner|co-owner|founder|co-founder|president|ceo|"
    r"chief executive|managing director|principal|proprietor|partner)\b",
    re.I,
)

# Minimum confidence score (0–10) to accept a LinkedIn match
_MIN_SCORE = 3


class LinkedInScraper:
    def __init__(self, timeout: int = 12, delay: float = 2.5):
        self.timeout = timeout
        self.delay = delay
        self._sess = requests.Session()
        self._sess.headers.update(_HEADERS)

    def find_owner(
        self,
        business_name: str,
        location: str = "",
        domain: str = "",
        email: str = "",
    ) -> dict:
        """
        Search for the business owner on LinkedIn.

        Returns:
            {
                "owner_name": str,       # empty if no confident match
                "linkedin_url": str,     # LinkedIn profile URL
                "confidence": int,       # 0-10 score
            }
        """
        empty = {"owner_name": "", "linkedin_url": "", "confidence": 0}
        if not business_name:
            return empty

        candidates = self._google_search(business_name, location)
        if not candidates:
            return empty

        best = self._pick_best(candidates, business_name, location, domain, email)
        if best and best["confidence"] >= _MIN_SCORE:
            return best
        return empty

    # ── Internal ──────────────────────────────────────────────────

    def _google_search(self, biz_name: str, location: str) -> list[dict]:
        """Return list of {name, url, snippet} from Google site:linkedin.com/in search."""
        q = f'site:linkedin.com/in "{biz_name}"'
        if location:
            # Add city (first word of location) to narrow results
            city = location.split(",")[0].strip().split()[0]
            q += f" {city}"
        q += " owner OR founder OR CEO OR president OR principal"

        url = f"https://www.google.com/search?q={quote_plus(q)}&num=10&hl=en"

        try:
            time.sleep(self.delay * random.uniform(0.8, 1.4))
            resp = self._sess.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return []
            return self._parse_google(resp.text)
        except Exception:
            return []

    def _parse_google(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        results = []

        for g in soup.select("div.g, div[data-sokoban-container], div.tF2Cxc"):
            a = g.find("a", href=True)
            if not a:
                continue
            href = a["href"]
            if "linkedin.com/in/" not in href:
                continue

            # Normalise: strip query params, keep /in/handle
            profile_url = _clean_li_url(href)
            if not profile_url:
                continue

            # Title line often has "Name - Title - Company | LinkedIn"
            title_el = g.select_one("h3")
            title_text = title_el.get_text(" ", strip=True) if title_el else ""

            # Snippet
            snippet_el = g.select_one("div.VwiC3b, span.aCOpRe, div[data-sncf]")
            snippet = snippet_el.get_text(" ", strip=True) if snippet_el else ""

            name = _extract_name(title_text)
            if not name:
                continue

            results.append(
                {"name": name, "url": profile_url, "snippet": title_text + " " + snippet}
            )

        return results

    def _pick_best(
        self,
        candidates: list[dict],
        biz_name: str,
        location: str,
        domain: str,
        email: str,
    ) -> dict | None:
        scored = []
        for c in candidates:
            score = _score(c, biz_name, location, domain, email)
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored:
            return None

        top_score, top = scored[0]
        return {
            "owner_name": top["name"],
            "linkedin_url": top["url"],
            "confidence": top_score,
        }


# ── Module-level helpers ──────────────────────────────────────────

def _clean_li_url(href: str) -> str:
    """Return a clean https://linkedin.com/in/handle URL or empty string."""
    m = re.search(r"(https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_%]+)", href)
    if m:
        return m.group(1).rstrip("/")
    # Google sometimes wraps in /url?q=
    m2 = re.search(r"[?&]q=(https?://[^&]+linkedin\.com/in/[^&]+)", href)
    if m2:
        from urllib.parse import unquote
        return unquote(m2.group(1)).rstrip("/")
    return ""


def _extract_name(title: str) -> str:
    """
    Pull a person name from a Google title like:
      "John Smith - Owner - ACME Plumbing | LinkedIn"
    Returns empty string if no plausible name found.
    """
    # Strip trailing | LinkedIn or - LinkedIn
    title = re.sub(r"\s*[\|\-]\s*LinkedIn.*$", "", title, flags=re.I).strip()
    # First segment before " - " is usually the name
    parts = re.split(r"\s+[-–]\s+", title)
    candidate = parts[0].strip()
    # Basic sanity: 2–4 words, each capitalised, no digits
    words = candidate.split()
    if 2 <= len(words) <= 4 and all(re.match(r"^[A-Z][a-z'\-]+$", w) for w in words):
        return candidate
    return ""


def _score(
    candidate: dict,
    biz_name: str,
    location: str,
    domain: str,
    email: str,
) -> int:
    score = 0
    text = candidate["snippet"].lower()
    name_lower = candidate["name"].lower()

    # Owner-ish title in snippet → strong signal
    if _OWNER_TITLES.search(text):
        score += 3

    # Business name words in snippet
    biz_words = [w.lower() for w in re.split(r"\W+", biz_name) if len(w) > 3]
    matched_biz = sum(1 for w in biz_words if w in text)
    if biz_words:
        score += min(3, int(matched_biz / max(len(biz_words), 1) * 3))

    # Location city/state in snippet
    if location:
        loc_words = [w.lower() for w in re.split(r"[\s,]+", location) if len(w) > 2]
        if any(w in text for w in loc_words):
            score += 2

    # Email local-part matches owner name initials or last name
    if email:
        local = email.split("@")[0].lower().replace(".", "").replace("_", "").replace("-", "")
        name_parts = name_lower.split()
        last = name_parts[-1] if name_parts else ""
        first = name_parts[0] if name_parts else ""
        if last and (last in local or local in last):
            score += 2
        elif first and (first in local or local in first):
            score += 1

    # Domain in snippet (e.g. company website mentioned)
    if domain and domain.lower().replace("www.", "") in text:
        score += 1

    return score
