#!/usr/bin/env bash
set -euo pipefail

readonly base_url="${1:-https://metro.9m-zx.com/mobility}"
readonly work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT

curl --fail --silent --show-error "${base_url}/health" >"${work_dir}/health.json"
python3 -m json.tool "${work_dir}/health.json" >/dev/null

curl --fail --silent --show-error \
  -H "Content-Type: application/json" \
  -d '{
    "flight_number": "CA1234",
    "departure_airport": "PEK",
    "terminal": "T3",
    "scheduled_departure": "2026-08-01T09:20:00+08:00",
    "departure_place": "北京市朝阳区望京（合成示例）",
    "checked_baggage": true,
    "risk_profile": "cautious"
  }' \
  "${base_url}/api/v1/decisions/preview" >"${work_dir}/decision.json"

python3 - "${work_dir}/decision.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    response = json.load(source)

assert response["verified"] is True
assert response["runtime"]["data_scope"] == "synthetic"
assert response["decision"]["recommended_leave_at"] == "2026-08-01T05:15:00+08:00"
print("Cloud smoke test passed: verified synthetic decision at 05:15.")
PY
