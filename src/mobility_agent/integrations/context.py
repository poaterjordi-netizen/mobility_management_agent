from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mobility_agent.api.settings import ApiSettings
from mobility_agent.domain.models import (
    AirportProcessSnapshot,
    Coordinates,
    DisruptionSignal,
    FlightSnapshot,
    JourneyContext,
    RiskProfile,
    RouteSnapshot,
    SourceMetadata,
    SourceStatus,
    TripInput,
    WeatherSnapshot,
)

PICKUP_MINUTES = {
    RiskProfile.STANDARD: 8,
    RiskProfile.CAUTIOUS: 12,
    RiskProfile.VERY_CAUTIOUS: 18,
}


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
    warnings: list[str] | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        source_id=source_id,
        source_name=source_name,
        source_type=source_type,
        observed_at=observed_at,
        fresh_until=(
            observed_at + timedelta(minutes=fresh_minutes)
            if fresh_minutes is not None
            else None
        ),
        scope=scope,
        completeness=completeness,
        freshness="fresh" if fresh_minutes is not None else "not_applicable",
        confidence=confidence,
        warnings=warnings or [],
    )


class AirportRegistry:
    def __init__(self, path: Path) -> None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.version = str(payload["registry_version"])
        self.airports: dict[str, dict[str, Any]] = payload["airports"]

    def airport(self, code: str) -> dict[str, Any] | None:
        return self.airports.get(code)


class JourneyContextBuilder:
    def __init__(self, settings: ApiSettings) -> None:
        self.settings = settings
        self.registry = AirportRegistry(settings.airport_registry_path)

    def build(
        self,
        trip: TripInput,
        *,
        observed_at: datetime | None = None,
    ) -> JourneyContext:
        observed = observed_at or datetime.now(UTC)
        warnings: list[str] = []
        missing_sources: list[str] = []

        flight = self._flight(trip, observed, warnings, missing_sources)
        airport = self._airport(trip, observed, warnings)
        route = self._route(trip, observed, warnings, missing_sources)
        weather = self._weather(trip, observed, warnings, missing_sources)
        disruptions = self._disruptions(trip, observed)

        source_types = {
            flight.metadata.source_type,
            route.metadata.source_type,
            weather.metadata.source_type,
        }
        live_types = {"official_api", "official_public"}
        live_count = sum(item in live_types for item in source_types)
        if live_count == 0:
            scope = "synthetic"
        elif live_count == len(source_types) and not missing_sources:
            scope = "live"
        else:
            scope = "mixed"

        return JourneyContext(
            observed_at=observed,
            data_scope=scope,
            flight=flight,
            airport=airport,
            route=route,
            weather=weather,
            disruptions=disruptions,
            missing_sources=sorted(set(missing_sources)),
            warnings=warnings,
        )

    def source_statuses(self) -> list[SourceStatus]:
        tesseract_available = bool(self.settings.ocr_command)
        flight_configured = bool(
            self.settings.flight_api_base and self.settings.flight_api_key
        )
        flight_enabled = flight_configured and self.settings.personal_data_enabled
        return [
            SourceStatus(
                source_id="flight-normalized-api",
                label="航班动态",
                category="flight",
                mode=(
                    "configured"
                    if flight_enabled
                    else "blocked"
                    if flight_configured
                    else "synthetic"
                ),
                freshness_minutes=10,
                requires_secret=True,
                enabled=flight_enabled,
                detail=(
                    "已配置规范化 HTTPS 航班接口；单次调用仍需用户同意"
                    if flight_enabled
                    else "接口已配置，但个人数据运行门禁未启用"
                    if flight_configured
                    else "未配置商业/官方航班凭据，使用用户确认计划与保守规则"
                ),
            ),
            SourceStatus(
                source_id=self.registry.version,
                label="机场数字孪生",
                category="airport",
                mode="available",
                freshness_minutes=None,
                requires_secret=False,
                enabled=True,
                detail=f"已登记 {len(self.registry.airports)} 个机场的版本化流程配置",
            ),
            SourceStatus(
                source_id="amap-driving-v5",
                label="高德路线",
                category="route",
                mode="configured" if self.settings.amap_web_service_key else "synthetic",
                freshness_minutes=15,
                requires_secret=True,
                enabled=bool(self.settings.amap_web_service_key),
                detail=(
                    "用户同意并提供坐标时由服务端调用"
                    if self.settings.amap_web_service_key
                    else "未配置服务端 Key，使用机场路线分位数基线"
                ),
            ),
            SourceStatus(
                source_id="open-meteo-airport",
                label="机场天气",
                category="weather",
                mode="available" if self.settings.public_data_enabled else "synthetic",
                freshness_minutes=30,
                requires_secret=False,
                enabled=self.settings.public_data_enabled,
                detail=(
                    "仅查询机场公开天气，不发送用户出发地"
                    if self.settings.public_data_enabled
                    else "公开天气开关未启用，使用零增量保守基线"
                ),
            ),
            SourceStatus(
                source_id="user-disruption-notes",
                label="活动、施工与事故信号",
                category="events",
                mode="available",
                freshness_minutes=None,
                requires_secret=False,
                enabled=True,
                detail="用户可粘贴已知信号；低置信信号只增加有限缓冲",
            ),
            SourceStatus(
                source_id="local-tesseract",
                label="截图 OCR",
                category="ocr",
                mode="available" if tesseract_available else "unavailable",
                freshness_minutes=None,
                requires_secret=False,
                enabled=tesseract_available,
                detail="图片在临时文件中本地识别，响应后立即删除",
            ),
            SourceStatus(
                source_id="assistant-provider",
                label="大模型解释",
                category="model",
                mode="configured" if self.settings.assistant_provider == "openai" else "synthetic",
                freshness_minutes=None,
                requires_secret=self.settings.assistant_provider == "openai",
                enabled=True,
                detail=(
                    f"已配置 {self.settings.assistant_model}，仅允许脱敏语义/派生证据"
                    if self.settings.assistant_provider == "openai"
                    else "使用确定性模板；不影响决策计算"
                ),
            ),
        ]

    def _flight(
        self,
        trip: TripInput,
        observed: datetime,
        warnings: list[str],
        missing: list[str],
    ) -> FlightSnapshot:
        if (
            self.settings.flight_api_base
            and self.settings.flight_api_key
            and self.settings.personal_data_enabled
            and trip.live_data_consent
        ):
            try:
                return self._live_flight(trip, observed)
            except (ValueError, KeyError, TypeError, urllib.error.URLError, TimeoutError):
                warnings.append("航班动态接口不可用，已回退到用户确认计划与保守时间窗。")
                missing.append("flight_live")
        else:
            missing.append("flight_live")
            if (
                self.settings.flight_api_base
                and self.settings.flight_api_key
                and not trip.live_data_consent
            ):
                warnings.append("未授权本次实时航班查询，使用用户确认计划。")

        scheduled = trip.scheduled_departure
        checkin_close_minutes = 50 if trip.checked_baggage else 40
        return FlightSnapshot(
            flight_number=trip.flight_number,
            status="scheduled",
            scheduled_departure=scheduled,
            terminal=trip.terminal,
            checkin_open_at=scheduled - timedelta(hours=2),
            checkin_close_at=scheduled - timedelta(minutes=checkin_close_minutes),
            boarding_start_at=scheduled - timedelta(minutes=45),
            boarding_close_at=scheduled - timedelta(minutes=15),
            delay_probability=0.15,
            metadata=_metadata(
                source_id="user-plan-plus-flight-policy",
                source_name="用户确认计划 + 合成航班规则",
                source_type="synthetic_rule",
                observed_at=observed,
                fresh_minutes=60,
                scope=f"{trip.flight_number}:{scheduled.date().isoformat()}",
                confidence=0.72,
                warnings=["不代表实时延误、登机口或航司特殊截止时间"],
            ),
        )

    def _live_flight(self, trip: TripInput, observed: datetime) -> FlightSnapshot:
        assert self.settings.flight_api_base
        assert self.settings.flight_api_key
        query = urllib.parse.urlencode(
            {
                "flight_number": trip.flight_number,
                "date": trip.scheduled_departure.date().isoformat(),
            }
        )
        request = urllib.request.Request(
            f"{self.settings.flight_api_base.rstrip('/')}/flight?{query}",
            headers={
                "Authorization": f"Bearer {self.settings.flight_api_key}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        scheduled = datetime.fromisoformat(payload["scheduled_departure"])
        return FlightSnapshot(
            flight_number=trip.flight_number,
            status=payload.get("status", "unknown"),
            scheduled_departure=scheduled,
            estimated_departure=(
                datetime.fromisoformat(payload["estimated_departure"])
                if payload.get("estimated_departure")
                else None
            ),
            terminal=str(payload.get("terminal") or trip.terminal),
            gate=payload.get("gate"),
            checkin_open_at=datetime.fromisoformat(payload["checkin_open_at"]),
            checkin_close_at=datetime.fromisoformat(payload["checkin_close_at"]),
            boarding_start_at=datetime.fromisoformat(payload["boarding_start_at"]),
            boarding_close_at=datetime.fromisoformat(payload["boarding_close_at"]),
            delay_probability=float(payload.get("delay_probability", 0.2)),
            metadata=_metadata(
                source_id="flight-normalized-api",
                source_name="获权规范化航班接口",
                source_type="official_api",
                observed_at=observed,
                fresh_minutes=10,
                scope=f"{trip.flight_number}:{scheduled.date().isoformat()}",
                confidence=0.94,
            ),
        )

    def _airport(
        self,
        trip: TripInput,
        observed: datetime,
        warnings: list[str],
    ) -> AirportProcessSnapshot:
        airport = self.registry.airport(trip.departure_airport)
        if not airport:
            warnings.append("机场不在首批数字孪生登记表中，使用保守通用流程。")
            return AirportProcessSnapshot(
                airport=trip.departure_airport,
                terminal=trip.terminal,
                checkin_minutes=35 if trip.checked_baggage else 20,
                security_minutes=30,
                walking_minutes=25,
                accessibility_extra_minutes=15 if trip.accessibility_assistance else 0,
                metadata=_metadata(
                    source_id="airport-generic-policy",
                    source_name="未登记机场保守规则",
                    source_type="synthetic_rule",
                    observed_at=observed,
                    fresh_minutes=None,
                    scope=trip.departure_airport,
                    completeness="partial",
                    confidence=0.55,
                    warnings=["航站楼和步行距离尚未完成现场核验"],
                ),
            )
        terminal_profiles = airport["terminals"]
        profile = terminal_profiles.get(trip.terminal)
        if profile is None:
            profile = next(iter(terminal_profiles.values()))
            warnings.append("航站楼未命中登记配置，使用该机场保守航站楼模板。")
        return AirportProcessSnapshot(
            airport=trip.departure_airport,
            terminal=trip.terminal,
            checkin_minutes=(
                int(profile["checkin_minutes"])
                if trip.checked_baggage
                else max(12, int(profile["checkin_minutes"]) - 12)
            ),
            security_minutes=int(profile["security_minutes"]),
            walking_minutes=int(profile["walking_minutes"]),
            gate_distance_meters=int(profile["gate_distance_meters"]),
            accessibility_extra_minutes=12 if trip.accessibility_assistance else 0,
            metadata=_metadata(
                source_id=self.registry.version,
                source_name=f"{airport['name']}版本化流程配置",
                source_type="configured_rule",
                observed_at=observed,
                fresh_minutes=None,
                scope=f"{trip.departure_airport}:{trip.terminal}",
                confidence=0.8,
            ),
        )

    def _route(
        self,
        trip: TripInput,
        observed: datetime,
        warnings: list[str],
        missing: list[str],
    ) -> RouteSnapshot:
        airport = self.registry.airport(trip.departure_airport)
        if (
            trip.live_data_consent
            and trip.departure_coordinates
            and airport
            and self.settings.amap_web_service_key
        ):
            try:
                return self._amap_route(
                    trip,
                    trip.departure_coordinates,
                    Coordinates(**airport["coordinates"]),
                    airport["name"],
                    observed,
                )
            except (ValueError, KeyError, TypeError, urllib.error.URLError, TimeoutError):
                warnings.append("实时路线调用失败，已回退到版本化路线分位数。")
                missing.append("route_live")
        else:
            missing.append("route_live")
            if trip.live_data_consent and not trip.departure_coordinates:
                warnings.append("已同意实时数据，但未提供坐标；未向地图发送文字住址。")

        baseline = (
            airport["route_baseline"]
            if airport
            else {"p50_minutes": 60, "p90_minutes": 85, "distance_km": None}
        )
        return RouteSnapshot(
            origin_label=trip.departure_place,
            destination_label=(
                airport["name"] if airport else f"{trip.departure_airport} 机场"
            ),
            distance_km=baseline.get("distance_km"),
            p50_minutes=int(baseline["p50_minutes"]),
            p90_minutes=int(baseline["p90_minutes"]),
            pickup_minutes=PICKUP_MINUTES[trip.risk_profile],
            congestion_level="unknown",
            metadata=_metadata(
                source_id=f"{self.registry.version}:route-baseline",
                source_name="版本化机场路线分位数",
                source_type="synthetic_rule",
                observed_at=observed,
                fresh_minutes=30,
                scope=f"{trip.departure_airport}:city-baseline",
                confidence=0.64,
                warnings=["未使用实时事故、施工和路段拥堵"],
            ),
        )

    def _amap_route(
        self,
        trip: TripInput,
        origin: Coordinates,
        destination: Coordinates,
        destination_name: str,
        observed: datetime,
    ) -> RouteSnapshot:
        query = urllib.parse.urlencode(
            {
                "key": self.settings.amap_web_service_key,
                "origin": f"{origin.longitude},{origin.latitude}",
                "destination": f"{destination.longitude},{destination.latitude}",
                "strategy": "32",
                "show_fields": "cost",
            }
        )
        request = urllib.request.Request(
            f"https://restapi.amap.com/v5/direction/driving?{query}",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        paths = payload["route"]["paths"]
        if not paths:
            raise ValueError("Amap returned no path")
        selected = paths[0]
        duration_seconds = int(selected.get("cost", {}).get("duration") or selected["duration"])
        p50 = max(1, math.ceil(duration_seconds / 60))
        distance = float(selected["distance"]) / 1000
        p90 = max(p50 + 8, math.ceil(p50 * 1.25))
        return RouteSnapshot(
            origin_label=trip.departure_place,
            destination_label=destination_name,
            distance_km=round(distance, 1),
            p50_minutes=p50,
            p90_minutes=p90,
            pickup_minutes=PICKUP_MINUTES[trip.risk_profile],
            congestion_level=(
                "high" if p90 >= p50 * 1.4 else "medium" if p90 >= p50 * 1.2 else "low"
            ),
            metadata=_metadata(
                source_id="amap-driving-v5",
                source_name="高德地图 Web 服务",
                source_type="official_api",
                observed_at=observed,
                fresh_minutes=15,
                scope=f"origin-token:{trip.departure_airport}",
                confidence=0.9,
            ),
        )

    def _weather(
        self,
        trip: TripInput,
        observed: datetime,
        warnings: list[str],
        missing: list[str],
    ) -> WeatherSnapshot:
        airport = self.registry.airport(trip.departure_airport)
        if self.settings.public_data_enabled and airport:
            try:
                return self._open_meteo_weather(
                    Coordinates(**airport["coordinates"]),
                    trip.scheduled_departure,
                    trip.departure_airport,
                    observed,
                )
            except (ValueError, KeyError, TypeError, urllib.error.URLError, TimeoutError):
                warnings.append("公开天气来源不可用，未增加未经证实的天气分钟。")
                missing.append("weather_live")
        else:
            missing.append("weather_live")
        return WeatherSnapshot(
            summary="暂无实时天气；天气风险未覆盖",
            severity="unknown",
            buffer_minutes=0,
            metadata=_metadata(
                source_id="weather-unavailable-policy",
                source_name="天气缺失策略",
                source_type="synthetic_rule",
                observed_at=observed,
                fresh_minutes=30,
                scope=trip.departure_airport,
                completeness="unavailable",
                confidence=0.35,
                warnings=["出发前应再次查看官方天气和预警"],
            ),
        )

    @staticmethod
    def _open_meteo_weather(
        coordinates: Coordinates,
        scheduled_departure: datetime,
        airport: str,
        observed: datetime,
    ) -> WeatherSnapshot:
        query = urllib.parse.urlencode(
            {
                "latitude": coordinates.latitude,
                "longitude": coordinates.longitude,
                "hourly": "precipitation_probability,wind_speed_10m,weather_code",
                "timezone": "Asia/Shanghai",
                "forecast_days": "16",
            }
        )
        request = urllib.request.Request(
            f"https://api.open-meteo.com/v1/forecast?{query}",
            headers={"Accept": "application/json", "User-Agent": "mobility-management-agent/0.3"},
        )
        with urllib.request.urlopen(request, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        hourly = payload["hourly"]
        target = scheduled_departure.replace(minute=0, second=0, microsecond=0)
        times = [datetime.fromisoformat(item) for item in hourly["time"]]
        index = min(
            range(len(times)),
            key=lambda item: abs(times[item] - target.replace(tzinfo=None)),
        )
        rain = int(hourly["precipitation_probability"][index] or 0)
        wind = float(hourly["wind_speed_10m"][index] or 0)
        code = int(hourly["weather_code"][index] or 0)
        severe = code >= 95 or wind >= 60 or rain >= 85
        moderate = code >= 61 or wind >= 40 or rain >= 60
        minor = code >= 51 or rain >= 30
        severity = "severe" if severe else "moderate" if moderate else "minor" if minor else "none"
        buffer = 25 if severe else 15 if moderate else 8 if minor else 0
        summary = f"降水概率 {rain}% · 风速 {wind:.0f} km/h"
        return WeatherSnapshot(
            summary=summary,
            severity=severity,
            precipitation_probability=rain,
            wind_speed_kph=wind,
            buffer_minutes=buffer,
            metadata=_metadata(
                source_id="open-meteo-airport",
                source_name="Open-Meteo 机场点位预报",
                source_type="official_public",
                observed_at=observed,
                fresh_minutes=30,
                scope=f"{airport}:airport-weather",
                confidence=0.78,
            ),
        )

    @staticmethod
    def _disruptions(trip: TripInput, observed: datetime) -> list[DisruptionSignal]:
        signals = []
        for index, note in enumerate(trip.user_disruption_notes):
            lowered = note.lower()
            if "封路" in note:
                category = "closure"
                minutes = 18
            elif "施工" in note or "修路" in note:
                category = "construction"
                minutes = 12
            elif "事故" in note or "车祸" in note:
                category = "accident"
                minutes = 15
            elif "活动" in note or "演唱会" in note or "赛事" in note:
                category = "event"
                minutes = 10
            else:
                category = "social_signal"
                minutes = 6
            if "合成" in note or "演练" in lowered:
                source_type = "synthetic_rule"
                source_name = "用户输入的合成事件"
            else:
                source_type = "user_confirmed"
                source_name = "用户报告的待核验信号"
            signals.append(
                DisruptionSignal(
                    signal_id=f"signal-{index + 1}",
                    category=category,
                    label=note,
                    impact_start=trip.scheduled_departure - timedelta(hours=5),
                    impact_end=trip.scheduled_departure,
                    impact_minutes=minutes,
                    route_intersection="possible",
                    metadata=_metadata(
                        source_id=f"user-signal-{index + 1}",
                        source_name=source_name,
                        source_type=source_type,
                        observed_at=observed,
                        fresh_minutes=60,
                        scope=f"{trip.departure_airport}:possible-route",
                        completeness="partial",
                        confidence=0.58,
                        warnings=["尚未由官方交通来源确认路线相交"],
                    ),
                )
            )
        return signals
