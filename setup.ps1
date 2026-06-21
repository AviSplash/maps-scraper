# ================================================================
# Google Maps Lead Scraper - Windows Setup
# Run once before first use:  .\setup.ps1
# ================================================================
param([switch]$Force)
$ErrorActionPreference = "Stop"

function Write-Step($m) { Write-Host "`n[*] $m" -ForegroundColor Cyan }
function Write-OK($m)   { Write-Host "[+] $m" -ForegroundColor Green }
function Write-Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }

Write-Host "================================================" -ForegroundColor Magenta
Write-Host "  Google Maps Lead Scraper - Setup" -ForegroundColor Magenta
Write-Host "================================================" -ForegroundColor Magenta

# -- 1. Find or install Python -------------------------------------
Write-Step "Checking for Python 3.9+..."
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(\d+)") {
            if ([int]$Matches[1] -ge 9) {
                $pythonCmd = $cmd
                Write-OK "Found $ver  ($cmd)"
                break
            } else {
                Write-Warn "Found $ver - need 3.9+"
            }
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Warn "Python 3.9+ not found - downloading installer..."
    $url  = "https://www.python.org/ftp/python/3.12.4/python-3.12.4-amd64.exe"
    $dest = "$env:TEMP\python-3.12.4-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
    Write-Host "  Installing (this takes ~1 minute)..."
    Start-Process -FilePath $dest -ArgumentList "/quiet","InstallAllUsers=1","PrependPath=1","Include_pip=1" -Wait
    Remove-Item $dest -ErrorAction SilentlyContinue
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")
    $pythonCmd = "python"
    Write-OK "Python 3.12 installed"
}

# -- 2. Virtual environment ----------------------------------------
Write-Step "Setting up virtual environment..."
if ((Test-Path ".venv") -and -not $Force) {
    Write-OK ".venv already exists  (pass -Force to recreate)"
} else {
    if (Test-Path ".venv") { Remove-Item ".venv" -Recurse -Force }
    & $pythonCmd -m venv .venv
    Write-OK ".venv created"
}

# -- 3. Dependencies -----------------------------------------------
Write-Step "Installing Python packages..."
& .venv\Scripts\pip.exe install --upgrade pip --quiet
& .venv\Scripts\pip.exe install -r requirements.txt --quiet
Write-OK "Packages installed"

# -- 4. Playwright browser -----------------------------------------
Write-Step "Installing Playwright / Chromium..."
& .venv\Scripts\playwright.exe install chromium
Write-OK "Chromium ready"

# -- Done ----------------------------------------------------------
Write-Host "`n================================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host @"

  QUICK START:
    .\run.ps1 -Keyword "HVAC contractors" -Location "Houston TX" -Max 50

  OR edit config.yaml then:
    .\run.ps1

  Output saved to: .\output\
"@ -ForegroundColor White
