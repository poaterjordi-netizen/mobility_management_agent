#!/usr/bin/env bash
set -euo pipefail

if [[ -x ".venv/bin/mobility-agent-api" ]]; then
  exec .venv/bin/mobility-agent-api
fi

if command -v mobility-agent-api >/dev/null 2>&1; then
  exec mobility-agent-api
fi

echo "mobility-agent-api is not installed; run: python3 -m pip install -e '.[dev]'" >&2
exit 1
