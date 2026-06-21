#!/usr/bin/env bash
# Xplogent installer (Linux / macOS).
set -e

echo "🧠 Installing Xplogent…"

# 1. Python check
if ! command -v python3 >/dev/null 2>&1; then
  echo "✗ python3 not found. Install Python 3.11+ first." >&2
  exit 1
fi
PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "• Python $PYV"

# 2. venv + install
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
echo "• Installing xplogent (this can take a minute)…"
pip install -e ".[all]"

# 3. Build the dashboard if Node is available
if command -v npm >/dev/null 2>&1; then
  echo "• Building the dashboard…"
  (cd web && npm install --no-audit --no-fund && npm run build)
else
  echo "• Node.js not found — skipping dashboard build."
  echo "  (Install Node 18+ and run 'cd web && npm install && npm run build' for the GUI.)"
fi

cat <<'DONE'

✓ Installed.

Next:
  source .venv/bin/activate
  xplogent setup      # choose your provider/model
  xplogent up         # launch the dashboard
DONE
