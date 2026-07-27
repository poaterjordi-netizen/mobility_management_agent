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
    "destination_airport": "SHA",
    "terminal": "T3",
    "scheduled_departure": "2026-08-01T09:20:00+08:00",
    "departure_place": "北京市朝阳区望京（合成示例）",
    "checked_baggage": true,
    "risk_profile": "cautious",
    "live_data_consent": false,
    "model_egress_consent": false,
    "user_disruption_notes": ["机场高速施工演练（合成）"]
  }' \
  "${base_url}/api/v1/decisions/preview" >"${work_dir}/decision.json"

python3 - "${work_dir}/decision.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    response = json.load(source)

assert response["verified"] is True
assert response["runtime"]["persistence"] == "none"
assert response["runtime"]["automatic_booking"] is False
assert len(response["evidence"]) == 8
assert response["decision"]["recommended_leave_at"] < response["decision"]["target_terminal_arrival"]
assert response["context"]["data_scope"] in {"synthetic", "mixed", "live"}
print(
    "Cloud smoke test passed:",
    response["context"]["data_scope"],
    response["decision"]["recommended_leave_at"],
)
PY
