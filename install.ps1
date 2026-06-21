# Xplogent installer (Windows / PowerShell).
$ErrorActionPreference = "Stop"

Write-Host "Installing Xplogent..."

# 1. Python check
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Error "python not found. Install Python 3.11+ first."
  exit 1
}

# 2. venv + install
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip | Out-Null
Write-Host "Installing xplogent (this can take a minute)..."
pip install -e ".[all]"

# 3. Build the dashboard if Node is available
if (Get-Command npm -ErrorAction SilentlyContinue) {
  Write-Host "Building the dashboard..."
  Push-Location web
  npm install --no-audit --no-fund
  npm run build
  Pop-Location
} else {
  Write-Host "Node.js not found - skipping dashboard build."
  Write-Host "Install Node 18+ and run 'cd web; npm install; npm run build' for the GUI."
}

Write-Host ""
Write-Host "Installed."
Write-Host "Next:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  xplogent setup      # choose your provider/model"
Write-Host "  xplogent up         # launch the dashboard"
