from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from pathlib import Path

from mobility_agent.api.settings import ApiSettings
from mobility_agent.domain.models import FlightTelemetrySnapshot, SourceMetadata, TripInput
from mobility_agent.integrations import JourneyContextBuilder
from mobility_agent.integrations.http_client import JsonHttpClient
from mobility_agent.integrations.live_data import (
    AdsbLolClient,
    AdvisoryRegistry,
    AirlineRegistry,
    AviationWeatherClient,
)

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.raw = json.dumps(payload).encode()

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return self.raw


class LiveDataTests(unittest.TestCase):
    observed = datetime.fromisoformat("2026-07-27T07:02:00+00:00")

    def test_adsb_parses_units_timestamp_and_uses_cache(self) -> None:
        calls = 0
        payload = {
            "now": 1785135720000,
            "ac": [
                {
                    "hex": "780abc",
                    "flight": "CCA1832 ",
                    "lat": 31.2,
                    "lon": 121.4,
                    "alt_baro": 10000,
                    "gs": 250,
                    "track": 92,
                    "seen": 1.5,
                }
            ],
        }

        def opener(*_args: object, **_kwargs: object) -> FakeResponse:
            nonlocal calls
            calls += 1
            return FakeResponse(payload)

        http = JsonHttpClient(
            allowed_hosts={"api.adsb.lol"},
            user_agent="test",
            opener=opener,
        )
        client = AdsbLolClient(http)
        first = client.lookup("CCA1832", observed_at=self.observed)
        second = client.lookup("CCA1832", observed_at=self.observed)

        self.assertIsNotNone(first)
        assert first is not None
        self.assertEqual(first.callsign, "CCA1832")
        self.assertEqual(first.state, "airborne")
        self.assertEqual(first.altitude_meters, 3048.0)
        self.assertEqual(first.groundspeed_kph, 463.0)
        self.assertEqual(first.metadata.source_type, "public_feed")
        self.assertEqual(
            first.metadata.fresh_until.isoformat(),
            "2026-07-27T07:03:58.500000+00:00",
        )
        self.assertEqual(second, first)
        self.assertEqual(calls, 1)

    def test_aviation_weather_parses_official_metar(self) -> None:
        payload = [
            {
                "rawOb": "METAR ZBAA 270700Z 18005MPS 9999 FEW040 34/22 Q1004",
                "reportTime": "2026-07-27T07:00:00Z",
                "fltCat": "VFR",
                "visib": "6.21",
                "wspd": 10,
                "temp": 34,
            }
        ]
        http = JsonHttpClient(
            allowed_hosts={"aviationweather.gov"},
            user_agent="test",
            opener=lambda *_args, **_kwargs: FakeResponse(payload),
        )
        result = AviationWeatherClient(http).metar("ZBAA", observed_at=self.observed)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.flight_category, "VFR")
        self.assertEqual(result.visibility_km, 10.0)
        self.assertEqual(result.wind_speed_kph, 18.5)
        self.assertEqual(result.observed_at.tzinfo, UTC)
        self.assertEqual(result.metadata.source_type, "official_public")

    def test_callsign_registry_and_official_advisory_match(self) -> None:
        airlines = AirlineRegistry(ROOT / "config" / "airlines.json")
        self.assertEqual(airlines.callsign("CA1832"), "CCA1832")
        self.assertIsNone(airlines.callsign("XX1234"))

        trip = TripInput(
            flight_number="MU5101",
            departure_airport="PVG",
            destination_airport="PEK",
            terminal="T1",
            scheduled_departure="2026-08-02T10:00:00+08:00",
            departure_place="上海市黄浦区永寿路附近",
        )
        signals = AdvisoryRegistry(ROOT / "config" / "public_advisories.json").match(
            trip, observed_at=self.observed
        )
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].category, "closure")
        self.assertEqual(signals[0].route_intersection, "possible")
        self.assertTrue(signals[0].metadata.source_url.startswith("https://www.shanghai.gov.cn/"))

    def test_http_client_rejects_non_allowlisted_url(self) -> None:
        client = JsonHttpClient(allowed_hosts={"api.adsb.lol"}, user_agent="test")
        with self.assertRaisesRegex(ValueError, "allowlist"):
            client.get("https://example.com/private")

    def test_context_rejects_same_callsign_far_from_departure_before_schedule(
        self,
    ) -> None:
        builder = JourneyContextBuilder(ApiSettings(environment="test", public_data_enabled=True))
        telemetry = FlightTelemetrySnapshot(
            callsign="CCA1506",
            icao24="780abc",
            state="airborne",
            latitude=32.42,
            longitude=117.27,
            last_contact_at=self.observed,
            metadata=SourceMetadata(
                source_id="test",
                source_name="test",
                source_type="public_feed",
                observed_at=self.observed,
                fresh_until=self.observed,
                scope="test",
                completeness="partial",
                freshness="fresh",
                confidence=0.7,
            ),
        )
        builder.adsb.lookup = lambda *_args, **_kwargs: telemetry  # type: ignore[method-assign]
        trip = TripInput(
            flight_number="CA1506",
            departure_airport="PVG",
            destination_airport="PEK",
            terminal="T2",
            scheduled_departure="2026-07-27T15:30:00+08:00",
            departure_place="公开测试点",
            live_data_consent=True,
        )
        warnings: list[str] = []

        result = builder._flight_telemetry(  # noqa: SLF001
            trip,
            datetime.fromisoformat("2026-07-27T15:27:00+08:00"),
            warnings,
        )

        self.assertIsNone(result)
        self.assertIn("已拒绝绑定", warnings[0])


if __name__ == "__main__":
    unittest.main()
