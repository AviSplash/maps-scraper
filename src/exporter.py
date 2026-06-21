"""
Export scraped leads to CSV, Excel (.xlsx), and/or JSON.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

_COLUMNS = [
    "name", "owner_name", "email", "phone",
    "address", "domain", "website", "category",
    "keyword", "search_location", "maps_url", "scraped_at",
]


class Exporter:
    def __init__(self, output_dir: str = "./output", formats: list = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.formats = [f.lower() for f in (formats or ["csv", "excel", "json"])]

    def export(self, results: list, keyword: str, location: str) -> dict:
        """Write results to all configured formats. Returns {format: filepath}."""
        if not results:
            print("  [!] No results to export.")
            return {}

        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_kw = keyword.replace(" ", "_").replace("/", "-")[:30]
        base    = f"{safe_kw}_{ts}"
        df      = self._build_df(results, keyword, location)
        paths   = {}

        for fmt in self.formats:
            try:
                path = self._write(df, base, fmt)
                paths[fmt] = str(path)
                print(f"  [→] {fmt.upper()}: {path}")
            except Exception as e:
                print(f"  [!] Export failed ({fmt}): {e}")

        return paths

    def _build_df(self, results: list, keyword: str, location: str) -> pd.DataFrame:
        now  = datetime.now().isoformat(timespec="seconds")
        rows = []
        for r in results:
            row = {col: r.get(col, "") for col in _COLUMNS}
            row.setdefault("keyword", keyword)
            row.setdefault("search_location", location)
            row["scraped_at"] = now
            if isinstance(row["email"], list):
                row["email"] = "; ".join(row["email"])
            rows.append(row)
        return pd.DataFrame(rows, columns=_COLUMNS)

    def _write(self, df: pd.DataFrame, base: str, fmt: str) -> Path:
        if fmt == "csv":
            p = self.output_dir / f"{base}.csv"
            df.to_csv(p, index=False, encoding="utf-8-sig")
        elif fmt in ("excel", "xlsx"):
            p = self.output_dir / f"{base}.xlsx"
            df.to_excel(p, index=False, engine="openpyxl")
        elif fmt == "json":
            p = self.output_dir / f"{base}.json"
            df.to_json(p, orient="records", indent=2, force_ascii=False)
        else:
            raise ValueError(f"Unknown format: {fmt}")
        return p
