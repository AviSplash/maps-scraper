# ================================================================
# Google Maps Lead Scraper — Launcher
# Run .\setup.ps1 first if this is your first time.
# ================================================================
param(
    [string]   $Keyword  = "",
    [string]   $Location = "",
    [int]      $Max      = 0,
    [string[]] $Format   = @(),
    [string]   $Output   = "",
    [switch]   $Headless,
    [switch]   $NoCrawl,
    [switch]   $NoN8n,
    [switch]   $Help
)

if ($Help) {
    Write-Host @"
Google Maps Lead Scraper

Usage:
  .\run.ps1 [options]

Options:
  -Keyword   <str>    Search keyword  (e.g. "HVAC contractors")
  -Location  <str>    Location        (e.g. "Houston TX")
  -Max       <int>    Max results per keyword (default: from config.yaml)
  -Format    <str[]>  Output formats: csv, excel, json
  -Output    <str>    Output directory (default ./output)
  -Headless           Run browser hidden (no window)
  -NoCrawl            Skip website crawling (faster, no emails)
  -NoN8n              Skip n8n AI enrichment
  -Help               Show this message

Examples:
  .\run.ps1 -Keyword "plumbers" -Location "Dallas TX" -Max 30
  .\run.ps1 -Keyword "HVAC" -Location "Austin TX" -Format csv -Headless
  .\run.ps1
"@ -ForegroundColor Cyan
    exit 0
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "[X] .venv not found. Run .\setup.ps1 first." -ForegroundColor Red
    exit 1
}

$pyArgs = @("src/main.py")
if ($Keyword)         { $pyArgs += "--keyword";  $pyArgs += $Keyword }
if ($Location)        { $pyArgs += "--location"; $pyArgs += $Location }
if ($Max -gt 0)       { $pyArgs += "--max";      $pyArgs += "$Max" }
if ($Format.Count -gt 0) { $pyArgs += "--format"; $pyArgs += $Format }
if ($Output)          { $pyArgs += "--output";   $pyArgs += $Output }
if ($Headless)        { $pyArgs += "--headless" }
if ($NoCrawl)         { $pyArgs += "--no-crawl" }
if ($NoN8n)           { $pyArgs += "--no-n8n" }

& .venv\Scripts\python.exe @pyArgs
