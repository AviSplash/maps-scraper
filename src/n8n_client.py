"""
n8n webhook client for AI-powered lead enrichment.

Expected webhook POST payload (full lead record + page_text):
  name, business_name (alias), email, phone, address, domain, website,
  category, keyword, search_location, maps_url, page_text

Expected webhook JSON response:
  owner_name   - string (empty if not found)
  notes        - optional string
"""

import requests


class N8nClient:
    def __init__(self, webhook_url: str, timeout: int = 30):
        self.webhook_url = (webhook_url or "").rstrip("/")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def enrich(self, business: dict, page_text: str) -> dict:
        """
        Send business data to n8n and return enriched fields.
        Returns {} on failure or when not enabled.
        """
        if not self.enabled:
            return {}

        email = business.get("email", "")
        if isinstance(email, list):
            email = "; ".join(email)

        payload = {
            "name":            business.get("name", ""),
            "business_name":   business.get("name", ""),   # alias for AI prompt
            "email":           email,
            "phone":           business.get("phone", ""),
            "address":         business.get("address", ""),
            "domain":          business.get("domain", ""),
            "website":         business.get("website", ""),
            "category":        business.get("category", ""),
            "keyword":         business.get("keyword", ""),
            "search_location": business.get("search_location", ""),
            "maps_url":        business.get("maps_url", ""),
            "page_text":       page_text,
        }

        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list):
                data = data[0] if data else {}

            return {
                "owner_name": str(data.get("owner_name", "")).strip(),
                "notes":      str(data.get("notes", "")).strip(),
            }

        except requests.exceptions.Timeout:
            print(f"    [!] n8n timeout ({self.timeout}s): {business.get('name')}")
        except requests.exceptions.HTTPError as e:
            print(f"    [!] n8n HTTP {e.response.status_code}: {business.get('name')}")
        except Exception as e:
            print(f"    [!] n8n error for {business.get('name')}: {e}")

        return {}
