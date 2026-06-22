# Xplogent installer (Windows / PowerShell). Installs once and adds to your PATH.
$ErrorActionPreference = "Stop"

Write-Host "Installing Xplogent..."

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Error "python not found. Install Python 3.11+ first."
  exit 1
}

# Prefer pipx (isolated, auto-on-PATH); fall back to a venv + PATH edit.
if (Get-Command pipx -ErrorAction SilentlyContinue) {
  Write-Host "Installing with pipx..."
  pipx install --force ".[all]"
  pipx ensurepath | Out-Null
  $run = "xplogent"
} else {
  Write-Host "pipx not found - using a virtualenv."
  python -m venv .venv
  & .\.venv\Scripts\Activate.ps1
  python -m pip install --upgrade pip | Out-Null
  pip install -e ".[all]"

  # Add the venv Scripts dir to the USER PATH (idempotent, no admin needed).
  $scripts = (Resolve-Path .\.venv\Scripts).Path
  $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
  if ($userPath -notlike "*$scripts*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$scripts", "User")
    Write-Host "Added $scripts to your user PATH (open a new terminal to use 'xplogent')."
  }
  $run = "$scripts\xplogent.exe"
}

# Build the dashboard if Node is available.
if (Get-Command npm -ErrorAction SilentlyContinue) {
  Write-Host "Building the dashboard..."
  Push-Location web; npm install --no-audit --no-fund; npm run build; Pop-Location
} else {
  Write-Host "Node.js not found - skipping dashboard build (GUI needs 'cd web; npm install; npm run build')."
}

Write-Host ""
Write-Host "Installed. Next:"
Write-Host "  $run setup      # choose your provider/model (one time)"
Write-Host "  $run start      # run in the background (survives closing PowerShell)"
Write-Host "  $run status     # check it"
Write-Host "  $run service install   # optional: auto-start at login"
