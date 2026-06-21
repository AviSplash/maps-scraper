"""
n8n webhook client for AI-powered lead enrichment.

Expected webhook POST payload:
  business_name, website, domain, address, phone, page_text

Expected webhook JSON response:
  owner_name   – string (empty if not found)
  notes        – optional string
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

        payload = {
            "business_name": business.get("name", ""),
            "website":       business.get("website", ""),
            "domain":        business.get("domain", ""),
            "address":       business.get("address", ""),
            "phone":         business.get("phone", ""),
            "page_text":     page_text,
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
