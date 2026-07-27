from __future__ import annotations

import json
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mobility_agent.domain.models import (
    AviationWeatherSnapshot,
    DisruptionSignal,
    FlightTelemetrySnapshot,
    SourceMetadata,
    TripInput,
)
from mobility_agent.integrations.http_client import JsonHttpClient


def _metadata(
    *,
    source_id: str,
    source_name: str,
    source_type: str,
    observed_at: datetime,
    fresh_minutes: int | None,
    scope: str,
    completeness: str = "complete",
    confidence: float,
    source_url: str,
    license_note: str,
    reference_at: datetime | None = None,
    warnings: list[str] | None = None,
) -> SourceMetadata:
    fresh_until = (
        observed_at + timedelta(minutes=fresh_minutes) if fresh_minutes is not None else None
    )
    return SourceMetadata(
        source_id=source_id,
        source_name=source_name,
        source_type=source_type,
        observed_at=observed_at,
        fresh_until=fresh_until,
        scope=scope,
        completeness=completeness,
        freshness=(
            "stale"
            if fresh_until is not None and reference_at is not None and reference_at > fresh_until
            else "fresh"
            if fresh_until is not None
            else "not_applicable"
        ),
        confidence=confidence,
        source_url=source_url,
        license_note=license_note,
        warnings=warnings or [],
    )


class AirlineRegistry:
    def __init__(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.version = str(payload["registry_version"])
        self.airlines: dict[str, dict[str, str]] = payload["airlines"]

    def callsign(self, flight_number: str) -> str | None:
        prefix = flight_number[:2]
        airline = self.airlines.get(prefix)
        if not airline:
            return None
        return f"{airline['icao']}{flight_number[2:]}"


class AdsbLolClient:
    source_url = "https://adsb.lol/"

    def __init__(self, http: JsonHttpClient) -> None:
        self.http = http

    def lookup(
        self,
        callsign: str,
        *,
        observed_at: datetime,
    ) -> FlightTelemetrySnapshot | None:
        encoded = urllib.parse.quote(callsign, safe="")
        endpoint = f"https://api.adsb.lol/v2/callsign/{encoded}"
        payload = self.http.get(endpoint, cache_ttl_seconds=20)
        aircraft = payload.get("ac") if isinstance(payload, dict) else None
        if not isinstance(aircraft, list) or not aircraft:
            return None
        record = aircraft[0]
        if not isinstance(record, dict):
            return None
        returned_callsign = str(record.get("flight") or "").strip().upper()
        if returned_callsign and returned_callsign != callsign.upper():
            return None
        last_contact = _adsb_timestamp(payload, record, observed_at)
        on_ground = record.get("alt_baro") == "ground"
        altitude = None if on_ground else _feet_to_meters(_number(record.get("alt_baro")))
        groundspeed = _knots_to_kph(_number(record.get("gs")))
        return FlightTelemetrySnapshot(
            callsign=returned_callsign or callsign.upper(),
            icao24=str(record.get("hex") or "unknown").strip(),
            state="ground" if on_ground else "airborne" if altitude is not None else "unknown",
            latitude=_number(record.get("lat")),
            longitude=_number(record.get("lon")),
            altitude_meters=altitude,
            groundspeed_kph=groundspeed,
            track_degrees=_number(record.get("track")),
            last_contact_at=last_contact,
            metadata=_metadata(
                source_id="adsb-lol-live",
                source_name="adsb.lol ADS-B 公共聚合",
                source_type="public_feed",
                observed_at=last_contact,
                fresh_minutes=2,
                scope=f"callsign:{callsign}",
                completeness="partial",
                confidence=0.78,
                source_url=self.source_url,
                license_note="公开 ADS-B 聚合；覆盖和航班号映射不保证完整",
                reference_at=observed_at,
                warnings=["仅表示当前可见的航空器遥测，不代表航司计划、值机或登机口"],
            ),
        )


class AviationWeatherClient:
    source_url = "https://aviationweather.gov/data/api/"

    def __init__(self, http: JsonHttpClient) -> None:
        self.http = http

    def metar(
        self,
        station_icao: str,
        *,
        observed_at: datetime,
    ) -> AviationWeatherSnapshot | None:
        query = urllib.parse.urlencode({"ids": station_icao, "format": "json"})
        payload = self.http.get(
            f"https://aviationweather.gov/api/data/metar?{query}",
            cache_ttl_seconds=60,
        )
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
            return None
        record = payload[0]
        report_time = _parse_utc(record.get("reportTime")) or observed_at
        visibility_miles = _number(record.get("visib"))
        return AviationWeatherSnapshot(
            station_icao=station_icao,
            raw_metar=str(record.get("rawOb") or "").strip()[:500],
            observed_at=report_time,
            flight_category=_flight_category(record.get("fltCat")),
            visibility_km=(
                round(visibility_miles * 1.609344, 1) if visibility_miles is not None else None
            ),
            wind_speed_kph=_knots_to_kph(_number(record.get("wspd"))),
            temperature_c=_number(record.get("temp")),
            metadata=_metadata(
                source_id="aviationweather-metar",
                source_name="美国航空气象中心 AviationWeather.gov",
                source_type="official_public",
                observed_at=report_time,
                fresh_minutes=90,
                scope=f"{station_icao}:airport-observation",
                confidence=0.92,
                source_url=self.source_url,
                license_note="美国政府航空气象公开数据；METAR 为机场当前观测而非未来预报",
                reference_at=observed_at,
            ),
        )


class AdvisoryRegistry:
    def __init__(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.version = str(payload["registry_version"])
        self.advisories: list[dict[str, Any]] = payload["advisories"]

    def match(self, trip: TripInput, *, observed_at: datetime) -> list[DisruptionSignal]:
        departure = trip.scheduled_departure
        haystack = f"{trip.departure_place} {trip.departure_airport}".lower()
        matches: list[DisruptionSignal] = []
        for item in self.advisories:
            impact_start = datetime.fromisoformat(item["impact_start"])
            impact_end = datetime.fromisoformat(item["impact_end"])
            if departure < impact_start or departure > impact_end:
                continue
            keywords = [str(value).lower() for value in item.get("route_keywords", [])]
            airport_codes = [str(value).upper() for value in item.get("airport_codes", [])]
            keyword_match = any(keyword in haystack for keyword in keywords)
            airport_match = trip.departure_airport in airport_codes
            if not keyword_match and not airport_match:
                continue
            published_at = datetime.fromisoformat(item["published_at"])
            possible_only = not bool(item.get("route_intersection_confirmed"))
            matches.append(
                DisruptionSignal(
                    signal_id=str(item["id"]),
                    category=item["category"],
                    label=str(item["title"]),
                    impact_start=impact_start,
                    impact_end=impact_end,
                    impact_minutes=int(item["impact_minutes"]),
                    route_intersection="possible" if possible_only else "confirmed",
                    metadata=_metadata(
                        source_id=self.version,
                        source_name=str(item["publisher"]),
                        source_type="official_public",
                        observed_at=published_at,
                        fresh_minutes=None,
                        scope=f"{trip.departure_airport}:route-advisory",
                        completeness="partial",
                        confidence=float(item["confidence"]),
                        source_url=str(item["source_url"]),
                        license_note="官方公开交通通告的版本化摘录；出发前需点击原文复核",
                        warnings=[
                            *(
                                ["仅按地点关键词判定可能相关，未确认实际路线穿越"]
                                if possible_only
                                else []
                            ),
                            *(
                                ["结束日期按公告所述约 34 个月估算，需打开原文复核"]
                                if item.get("end_is_estimated")
                                else []
                            ),
                        ],
                    ),
                )
            )
        return matches


def _number(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        normalized = str(value).strip().lstrip("<>").rstrip("+")
        return float(normalized)
    except (TypeError, ValueError):
        return None


def _feet_to_meters(value: float | None) -> float | None:
    return round(value * 0.3048, 1) if value is not None else None


def _knots_to_kph(value: float | None) -> float | None:
    return round(value * 1.852, 1) if value is not None else None


def _parse_utc(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _adsb_timestamp(
    payload: dict[str, Any],
    record: dict[str, Any],
    fallback: datetime,
) -> datetime:
    now_value = _number(payload.get("now"))
    seen = _number(record.get("seen")) or 0
    if now_value is None:
        return fallback
    seconds = now_value / 1000 if now_value > 10_000_000_000 else now_value
    return datetime.fromtimestamp(seconds - seen, tz=UTC)


def _flight_category(value: object) -> str:
    normalized = str(value or "UNKNOWN").upper()
    return normalized if normalized in {"VFR", "MVFR", "IFR", "LIFR"} else "UNKNOWN"
