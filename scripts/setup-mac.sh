#!/usr/bin/env bash
# Reproducible local host setup; optional packages are explicit opt-ins.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v python3.13 >/dev/null || { echo 'Install Python 3.13 (brew install python@3.13).'; exit 1; }
node -e 'if(process.versions.node!=="24.4.1") { console.error("Use Node 24.4.1: nvm install && nvm use"); process.exit(1) }'
if [[ -x backend/.venv/bin/python ]]; then
  backend/.venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3,13), "Existing venv is not Python 3.13; recreate it after preserving any local files"'
else
  python3.13 -m venv backend/.venv
fi
backend/.venv/bin/python -m pip install -r backend/requirements.txt
for optional in "$@"; do
  case "$optional" in
    vision|ocr|joystick|ai) backend/.venv/bin/python -m pip install -r "backend/requirements-$optional.txt" ;;
    firmware) backend/.venv/bin/python -m pip install platformio==6.1.18 ;;
    *) echo "Unknown option: $optional (vision, ocr, joystick, ai, firmware)"; exit 1 ;;
  esac
done
npm --prefix frontend ci
