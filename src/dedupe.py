"""
SQLite-backed duplicate tracker.

Keeps a local record of every lead already processed so re-runs (and the same
business matching multiple keywords) skip the expensive crawl + AI steps.

Key: the Google Maps listing URL (stable per business). Falls back to a
normalized "name|address" when no maps_url is present.
"""

import sqlite3
from datetime import datetime
from pathlib import Path


def lead_key(biz: dict) -> str:
    """Return a stable dedupe key for a scraped business."""
    url = (biz.get("maps_url") or "").strip()
    if url:
        return url.split("?")[0].rstrip("/").lower()
    name = (biz.get("name") or "").strip().lower()
    addr = (biz.get("address") or "").strip().lower()
    return f"{name}|{addr}"


class LeadStore:
    def __init__(self, db_path: str = "./leads.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_leads (
                key        TEXT PRIMARY KEY,
                name       TEXT,
                address    TEXT,
                maps_url   TEXT,
                first_seen TEXT
            )
            """
        )
        self.conn.commit()

    def seen(self, key: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM seen_leads WHERE key = ? LIMIT 1", (key,)
        )
        return cur.fetchone() is not None

    def add(self, key: str, biz: dict) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO seen_leads (key, name, address, maps_url, first_seen) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                key,
                biz.get("name", ""),
                biz.get("address", ""),
                biz.get("maps_url", ""),
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()

    def filter_new(self, results: list) -> tuple:
        """Split results into (new_leads, duplicate_count), recording new ones."""
        new_leads = []
        dupes = 0
        for biz in results:
            key = lead_key(biz)
            if self.seen(key):
                dupes += 1
                continue
            self.add(key, biz)
            new_leads.append(biz)
        return new_leads, dupes

    def close(self) -> None:
        self.conn.close()
