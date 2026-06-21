# Google Maps Lead Scraper

Scrapes Google Maps for business leads using keywords. Runs locally on Windows, exports CSV / Excel / JSON. Optionally enriches leads with owner names via n8n + Claude Haiku AI.

## Fields extracted

| Field | Source |
|---|---|
| Business name | Google Maps |
| Phone | Google Maps |
| Address | Google Maps |
| Website / Domain | Google Maps |
| Category | Google Maps |
| Email(s) | Website crawl |
| Owner name | n8n + AI (optional) |

---

## Quick start (Windows)

### 1. Setup (run once)

```powershell
.\setup.ps1
```

This installs Python 3.12 (if needed), creates a virtual environment, installs all packages, and downloads the Chromium browser.

### 2. Configure

Edit `config.yaml`:

```yaml
keywords:
  - "HVAC contractors"
  - "plumbers"
location: "Houston, TX"
max_results: 50
```

### 3. Run

```powershell
# Use config.yaml defaults
.\run.ps1

# Override on the command line
.\run.ps1 -Keyword "electricians" -Location "Dallas TX" -Max 30

# Headless (no browser window)
.\run.ps1 -Headless

# Skip website crawling (faster, no emails)
.\run.ps1 -NoCrawl
```

Output files land in `./output/` as CSV, Excel, and JSON.

---

## Command reference

```
.\run.ps1 [-Keyword <str>] [-Location <str>] [-Max <int>]
          [-Format csv|excel|json] [-Output <dir>]
          [-Headless] [-NoCrawl] [-NoN8n] [-Help]
```

| Flag | Default | Description |
|---|---|---|
| `-Keyword` | config.yaml | Search keyword |
| `-Location` | config.yaml | City / state |
| `-Max` | 50 | Max results per keyword |
| `-Format` | csv excel json | Output format(s) |
| `-Output` | `./output` | Output directory |
| `-Headless` | off | Hide browser window |
| `-NoCrawl` | off | Skip email crawling |
| `-NoN8n` | off | Skip AI enrichment |
| `-NoDedupe` | off | Disable the SQLite duplicate filter |

---

## Duplicate prevention

The scraper keeps a local SQLite file (`leads.db`) of every business it has
already processed, keyed on the Google Maps listing URL. On every run it skips
leads it has seen before — *before* the website crawl and AI enrichment — so you
don't waste time or API cost re-processing them, and the same business matching
multiple keywords is only collected once.

```yaml
dedupe:
  enabled: true
  db_path: "./leads.db"
```

Disable per-run with `.\run.ps1 -NoDedupe`, or delete `leads.db` to start fresh.
When exporting to Google Sheets via n8n, the workflow also uses *Append or Update*
keyed on `maps_url`, so the sheet stays duplicate-free as a second layer.

---

## n8n AI enrichment (owner name)

The scraper sends each lead's website text to n8n, which calls Claude Haiku to extract the owner/founder name.

### Setup

1. Import `n8n/workflow_template.json` into your n8n instance
   - n8n → Workflows → Import from File
2. Add your Anthropic API key as an **HTTP Header Auth** credential:
   - Name: `Anthropic API Key`
   - Header name: `x-api-key`
   - Value: `sk-ant-...`
3. Activate the workflow and copy the **Production** webhook URL
4. Paste it into `config.yaml`:

```yaml
n8n:
  enabled: true
  webhook_url: "http://localhost:5678/webhook/leads"
  timeout: 30
```

> **Tip:** Claude Haiku is ~25x cheaper than GPT-4o. Expected cost: ~$0.001 per lead.

---

## Notes

- Run with `headless: false` (visible browser) for best reliability — Google is less likely to block a visible browser session.
- For batches over 100 leads, add delays in `config.yaml` (`delay_between_results: 3`).
- Email extraction crawls the homepage plus up to 3 sub-pages (contact, about, team).
- If Google prompts a CAPTCHA, pause and solve it manually — the browser window is open and interactive.
