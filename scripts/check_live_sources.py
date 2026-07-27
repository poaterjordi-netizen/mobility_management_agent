#!/usr/bin/env python3
"""Read-only production diagnostic for the credential-free public sources."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mobility_agent.integrations.http_client import JsonHttpClient  # noqa: E402
from mobility_agent.integrations.live_data import (  # noqa: E402
    AdsbLolClient,
    AviationWeatherClient,
)


def main() -> int:
    observed = datetime.now(UTC)
    http = JsonHttpClient(
        allowed_hosts={"api.adsb.lol", "aviationweather.gov"},
        user_agent="mobility-management-agent-live-check/0.4",
        timeout_seconds=8,
        retries=1,
        cache_ttl_seconds=10,
    )
    metar = AviationWeatherClient(http).metar("ZBAA", observed_at=observed)
    nearby = http.get(
        "https://api.adsb.lol/v2/point/31.1443/121.8052/250",
        cache_ttl_seconds=10,
    )
    records = nearby.get("ac", []) if isinstance(nearby, dict) else []
    callsigns = sorted(
        {
            str(record.get("flight") or "").strip()
            for record in records
            if isinstance(record, dict) and str(record.get("flight") or "").strip()
        }
    )
    telemetry = None
    if callsigns:
        telemetry = AdsbLolClient(http).lookup(callsigns[0], observed_at=observed)

    output = {
        "checked_at": observed.isoformat(),
        "aviation_weather": metar.model_dump(mode="json") if metar else None,
        "adsb_near_pvg": {
            "aircraft_count": len(records),
            "sample_callsigns": callsigns[:5],
            "sample_telemetry": telemetry.model_dump(mode="json") if telemetry else None,
            "source_url": "https://adsb.lol/",
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if metar and records else 2


if __name__ == "__main__":
    raise SystemExit(main())
