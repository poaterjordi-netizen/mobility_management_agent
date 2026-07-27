from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mobility_agent.api.settings import ApiSettings
from mobility_agent.domain.models import (
    AirportProcessSnapshot,
    AviationWeatherSnapshot,
    Coordinates,
    DisruptionSignal,
    FlightSnapshot,
    FlightTelemetrySnapshot,
    JourneyContext,
    RiskProfile,
    RouteSnapshot,
    SourceMetadata,
    SourceStatus,
    TripInput,
    WeatherSnapshot,
)
from mobility_agent.integrations.http_client import JsonHttpClient, UpstreamError
from mobility_agent.integrations.live_data import (
    AdsbLolClient,
    AdvisoryRegistry,
    AirlineRegistry,
    AviationWeatherClient,
)

PICKUP_MINUTES = {
    RiskProfile.STANDARD: 8,
    RiskProfile.CAUTIOUS: 12,
    RiskProfile.VERY_CAUTIOUS: 18,
}
AMAP_LIVE_ROUTE_WINDOW = timedelta(hours=3)


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
    source_url: str | None = None,
    license_note: str | None = None,
    warnings: list[str] | None = None,
) -> SourceMetadata:
    return SourceMetadata(
        source_id=source_id,
        source_name=source_name,
        source_type=source_type,
        observed_at=observed_at,
        fresh_until=(
            observed_at + timedelta(minutes=fresh_minutes) if fresh_minutes is not None else None
        ),
        scope=scope,
        completeness=completeness,
        freshness="fresh" if fresh_minutes is not None else "not_applicable",
        confidence=confidence,
        source_url=source_url,
        license_note=license_note,
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
        self.airlines = AirlineRegistry(settings.airline_registry_path)
        self.advisories = AdvisoryRegistry(settings.advisory_registry_path)
        self.public_http = JsonHttpClient(
            allowed_hosts={
                "api.adsb.lol",
                "aviationweather.gov",
                "api.open-meteo.com",
                "restapi.amap.com",
            },
            user_agent="mobility-management-agent/0.4.1 (+https://metro.9m-zx.com/mobility/)",
            timeout_seconds=settings.public_http_timeout_seconds,
            retries=settings.public_http_retries,
            cache_ttl_seconds=settings.public_http_cache_seconds,
        )
        self.adsb = AdsbLolClient(self.public_http)
        self.aviation_weather_client = AviationWeatherClient(self.public_http)

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
        weather_warnings: list[str] = []
        weather_missing: list[str] = []
        telemetry_warnings: list[str] = []
        aviation_warnings: list[str] = []
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="mobility-public") as pool:
            weather_future = pool.submit(
                self._weather,
                trip,
                observed,
                weather_warnings,
                weather_missing,
            )
            telemetry_future = pool.submit(
                self._flight_telemetry,
                trip,
                observed,
                telemetry_warnings,
            )
            aviation_future = pool.submit(
                self._aviation_weather,
                trip,
                observed,
                aviation_warnings,
            )
            weather = weather_future.result()
            flight_telemetry = telemetry_future.result()
            aviation_weather = aviation_future.result()
        warnings.extend(weather_warnings)
        warnings.extend(telemetry_warnings)
        warnings.extend(aviation_warnings)
        missing_sources.extend(weather_missing)
        disruptions = [
            *self._disruptions(trip, observed),
            *self.advisories.match(trip, observed_at=observed),
        ]

        source_types = {
            flight.metadata.source_type,
            route.metadata.source_type,
            weather.metadata.source_type,
        }
        live_types = {"official_api", "official_public", "public_feed"}
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
            flight_telemetry=flight_telemetry,
            aviation_weather=aviation_weather,
            disruptions=disruptions,
            missing_sources=sorted(set(missing_sources)),
            warnings=warnings,
        )

    def source_statuses(self) -> list[SourceStatus]:
        tesseract_available = bool(self.settings.ocr_command)
        flight_configured = bool(self.settings.flight_api_base and self.settings.flight_api_key)
        flight_enabled = flight_configured and self.settings.personal_data_enabled
        return [
            SourceStatus(
                source_id="adsb-lol-live",
                label="实时航空器遥测",
                category="flight",
                mode="available" if self.settings.public_data_enabled else "blocked",
                freshness_minutes=2,
                requires_secret=False,
                enabled=self.settings.public_data_enabled,
                detail=(
                    "用户同意且航班临近时，按航班呼号查询公开 ADS-B；不代表航司计划或登机口"
                    if self.settings.public_data_enabled
                    else "公开数据开关未启用"
                ),
            ),
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
                freshness_minutes=5,
                requires_secret=True,
                enabled=bool(self.settings.amap_web_service_key),
                detail=(
                    "用户同意、提供坐标且进入预计离家前 3 小时时，由服务端调用当前驾车路线"
                    if self.settings.amap_web_service_key
                    else "未配置服务端 Key，使用机场路线分位数基线"
                ),
            ),
            SourceStatus(
                source_id="amap-future-driving-v4",
                label="高德未来路径规划",
                category="route",
                mode="blocked",
                freshness_minutes=None,
                requires_secret=True,
                enabled=False,
                detail="未来 7 天 ETD 属于企业高级服务，当前账号未获权；更早阶段使用路线基线",
            ),
            SourceStatus(
                source_id="open-meteo-airport",
                label="出发地与机场天气",
                category="weather",
                mode="available" if self.settings.public_data_enabled else "synthetic",
                freshness_minutes=30,
                requires_secret=False,
                enabled=self.settings.public_data_enabled,
                detail=(
                    "机场点位默认查询；用户同意并提供坐标时同时查询出发地并取较高风险"
                    if self.settings.public_data_enabled
                    else "公开天气开关未启用，使用零增量保守基线"
                ),
            ),
            SourceStatus(
                source_id="aviationweather-metar",
                label="机场实况 METAR",
                category="weather",
                mode="available" if self.settings.public_data_enabled else "blocked",
                freshness_minutes=90,
                requires_secret=False,
                enabled=self.settings.public_data_enabled,
                detail="AviationWeather.gov 官方机场观测；与未来预报分开展示",
            ),
            SourceStatus(
                source_id=self.advisories.version,
                label="官方交通通告",
                category="events",
                mode="available",
                freshness_minutes=None,
                requires_secret=False,
                enabled=True,
                detail=f"版本化收录 {len(self.advisories.advisories)} 条官方公开通告并按时空匹配",
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
            except (
                UpstreamError,
                ValueError,
                KeyError,
                TypeError,
                urllib.error.URLError,
                TimeoutError,
            ):
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
        baseline = (
            airport["route_baseline"]
            if airport
            else {"p50_minutes": 60, "p90_minutes": 85, "distance_km": None}
        )
        estimated_leave_at = trip.scheduled_departure.astimezone(UTC) - timedelta(
            minutes=(
                120
                + int(baseline["p90_minutes"])
                + PICKUP_MINUTES[trip.risk_profile]
                + 10
            )
        )
        until_estimated_leave = estimated_leave_at - observed.astimezone(UTC)
        within_live_window = (
            -timedelta(minutes=30) <= until_estimated_leave <= AMAP_LIVE_ROUTE_WINDOW
        )
        if (
            trip.live_data_consent
            and trip.departure_coordinates
            and airport
            and self.settings.amap_web_service_key
            and within_live_window
        ):
            terminal = airport.get("terminals", {}).get(trip.terminal, {})
            destination_coordinates = terminal.get("coordinates", airport["coordinates"])
            try:
                return self._amap_route(
                    trip,
                    trip.departure_coordinates,
                    Coordinates(**destination_coordinates),
                    f"{airport['name']} {trip.terminal}",
                    observed,
                )
            except (
                UpstreamError,
                ValueError,
                KeyError,
                TypeError,
                urllib.error.URLError,
                TimeoutError,
            ):
                warnings.append("实时路线调用失败，已回退到版本化路线分位数。")
                missing.append("route_live")
        else:
            missing.append("route_live")
            if trip.live_data_consent and not trip.departure_coordinates:
                warnings.append("已同意实时数据，但未提供坐标；未向地图发送文字住址。")
            elif (
                trip.live_data_consent
                and trip.departure_coordinates
                and airport
                and self.settings.amap_web_service_key
                and not within_live_window
            ):
                warnings.append("高德当前路况仅在预计离家前 3 小时内使用；现阶段采用路线基线。")
        return RouteSnapshot(
            origin_label=trip.departure_place,
            destination_label=(airport["name"] if airport else f"{trip.departure_airport} 机场"),
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
                "show_fields": "cost,tmcs",
                "alternative_route": "3",
            }
        )
        payload = self.public_http.get(
            f"https://restapi.amap.com/v5/direction/driving?{query}",
            cache_ttl_seconds=120,
        )
        if payload.get("status") != "1" or payload.get("infocode") != "10000":
            raise UpstreamError("Amap rejected the route request")
        paths = payload["route"]["paths"]
        if not paths:
            raise ValueError("Amap returned no path")
        selected = paths[0]
        duration_seconds = int(selected["cost"]["duration"])
        p50 = max(1, math.ceil(duration_seconds / 60))
        distance = float(selected["distance"]) / 1000
        congestion_level, congestion_summary = _amap_congestion(selected.get("steps", []))
        p90_factor = {"low": 1.15, "medium": 1.25, "high": 1.4}[congestion_level]
        minimum_spread = {"low": 8, "medium": 10, "high": 15}[congestion_level]
        p90 = max(p50 + minimum_spread, math.ceil(p50 * p90_factor))
        return RouteSnapshot(
            origin_label=trip.departure_place,
            destination_label=destination_name,
            distance_km=round(distance, 1),
            p50_minutes=p50,
            p90_minutes=p90,
            pickup_minutes=PICKUP_MINUTES[trip.risk_profile],
            congestion_level=congestion_level,
            metadata=_metadata(
                source_id="amap-driving-v5",
                source_name="高德地图实时驾车路线",
                source_type="official_api",
                observed_at=observed,
                fresh_minutes=5,
                scope=f"origin-token:{trip.departure_airport}:{trip.terminal}",
                confidence=0.92,
                source_url="https://lbs.amap.com/api/webservice/guide/api/newroute",
                license_note="高德地图 Web 服务测试 Key；仅服务端持有并限制服务器出口 IP",
                warnings=[
                    congestion_summary,
                    "P50 是高德当前推荐路线 ETA；P90 是确定性保守上界，不是供应商统计分位数",
                    "当前路况只用于预计离家前 3 小时内的临近决策",
                ],
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
                airport_weather = self._open_meteo_weather(
                    Coordinates(**airport["coordinates"]),
                    trip.scheduled_departure,
                    trip.departure_airport,
                    observed,
                )
                if trip.live_data_consent and trip.departure_coordinates:
                    origin_weather = self._open_meteo_weather(
                        trip.departure_coordinates,
                        trip.scheduled_departure,
                        "origin",
                        observed,
                    )
                    return self._combine_route_weather(
                        origin_weather,
                        airport_weather,
                        observed,
                        trip.departure_airport,
                    )
                return airport_weather
            except (
                UpstreamError,
                ValueError,
                KeyError,
                TypeError,
                urllib.error.URLError,
                TimeoutError,
            ):
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
    def _combine_route_weather(
        origin: WeatherSnapshot,
        airport: WeatherSnapshot,
        observed: datetime,
        airport_code: str,
    ) -> WeatherSnapshot:
        severity_order = {
            "unknown": -1,
            "none": 0,
            "minor": 1,
            "moderate": 2,
            "severe": 3,
        }
        selected = max(
            (origin, airport),
            key=lambda item: (severity_order[item.severity], item.buffer_minutes),
        )
        precipitation_values = [
            item.precipitation_probability
            for item in (origin, airport)
            if item.precipitation_probability is not None
        ]
        wind_values = [
            item.wind_speed_kph for item in (origin, airport) if item.wind_speed_kph is not None
        ]
        return WeatherSnapshot(
            summary=f"出发地 {origin.summary}；机场 {airport.summary}",
            severity=selected.severity,
            precipitation_probability=(max(precipitation_values) if precipitation_values else None),
            wind_speed_kph=max(wind_values) if wind_values else None,
            buffer_minutes=max(origin.buffer_minutes, airport.buffer_minutes),
            metadata=_metadata(
                source_id="open-meteo-route-weather",
                source_name="Open-Meteo 出发地与机场点位预报",
                source_type="public_feed",
                observed_at=observed,
                fresh_minutes=30,
                scope=f"origin-token:{airport_code}:route-weather",
                confidence=min(origin.metadata.confidence, airport.metadata.confidence),
                source_url="https://open-meteo.com/en/docs",
                license_note="经用户同意查询出发地坐标与机场公开坐标，不记录坐标",
            ),
        )

    def _open_meteo_weather(
        self,
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
        endpoint = f"https://api.open-meteo.com/v1/forecast?{query}"
        payload = self.public_http.get(endpoint, cache_ttl_seconds=30 * 60)
        hourly = payload["hourly"]
        target = scheduled_departure.replace(minute=0, second=0, microsecond=0)
        times = [datetime.fromisoformat(item) for item in hourly["time"]]
        index = min(
            range(len(times)),
            key=lambda item: abs(times[item] - target.replace(tzinfo=None)),
        )
        if abs(times[index] - target.replace(tzinfo=None)) > timedelta(hours=2):
            raise ValueError("requested departure is outside the forecast horizon")
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
                source_type="public_feed",
                observed_at=observed,
                fresh_minutes=30,
                scope=f"{airport}:airport-weather",
                confidence=0.78,
                source_url="https://open-meteo.com/en/docs",
                license_note="Open-Meteo 公开天气预报；机场坐标点位查询",
            ),
        )

    def _flight_telemetry(
        self,
        trip: TripInput,
        observed: datetime,
        warnings: list[str],
    ) -> FlightTelemetrySnapshot | None:
        seconds_from_schedule = (
            observed.astimezone(UTC) - trip.scheduled_departure.astimezone(UTC)
        ).total_seconds()
        if not (
            self.settings.public_data_enabled
            and trip.live_data_consent
            and -3 * 60 * 60 <= seconds_from_schedule <= 8 * 60 * 60
        ):
            return None
        callsign = self.airlines.callsign(trip.flight_number)
        if callsign is None:
            return None
        try:
            telemetry = self.adsb.lookup(callsign, observed_at=observed)
            airport = self.registry.airport(trip.departure_airport)
            if (
                telemetry
                and airport
                and telemetry.latitude is not None
                and telemetry.longitude is not None
                and seconds_from_schedule <= 0
            ):
                coordinates = Coordinates(**airport["coordinates"])
                distance = _distance_km(
                    telemetry.latitude,
                    telemetry.longitude,
                    coordinates.latitude,
                    coordinates.longitude,
                )
                if distance > 200:
                    warnings.append(
                        "发现同号 ADS-B 航空器，但与计划出发机场/时段不一致，已拒绝绑定。"
                    )
                    return None
            return telemetry
        except (UpstreamError, ValueError, KeyError, TypeError):
            warnings.append("公开 ADS-B 航班遥测暂时不可用；不影响已确认的计划时间。")
            return None

    def _aviation_weather(
        self,
        trip: TripInput,
        observed: datetime,
        warnings: list[str],
    ) -> AviationWeatherSnapshot | None:
        airport = self.registry.airport(trip.departure_airport)
        station = str(airport.get("icao") or "") if airport else ""
        if not self.settings.public_data_enabled or not station:
            return None
        try:
            return self.aviation_weather_client.metar(station, observed_at=observed)
        except (UpstreamError, ValueError, KeyError, TypeError):
            warnings.append("机场 METAR 实况暂时不可用；仍保留独立的未来天气预报。")
            return None

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


def _distance_km(
    first_latitude: float,
    first_longitude: float,
    second_latitude: float,
    second_longitude: float,
) -> float:
    radius_km = 6_371.0
    first_latitude_radians = math.radians(first_latitude)
    second_latitude_radians = math.radians(second_latitude)
    latitude_delta = math.radians(second_latitude - first_latitude)
    longitude_delta = math.radians(second_longitude - first_longitude)
    value = (
        math.sin(latitude_delta / 2) ** 2
        + math.cos(first_latitude_radians)
        * math.cos(second_latitude_radians)
        * math.sin(longitude_delta / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _amap_congestion(steps: list[dict[str, Any]]) -> tuple[str, str]:
    distances = {
        "畅通": 0,
        "缓行": 0,
        "拥堵": 0,
        "严重拥堵": 0,
        "未知": 0,
    }
    for step in steps:
        for segment in step.get("tmcs", []):
            status = str(segment.get("tmc_status") or "未知")
            distance = max(0, int(float(segment.get("tmc_distance") or 0)))
            distances[status if status in distances else "未知"] += distance

    known_distance = sum(distances[name] for name in ("畅通", "缓行", "拥堵", "严重拥堵"))
    if known_distance == 0:
        return "medium", "高德未返回可用路况分段，采用中等拥堵缓冲"

    slow_ratio = (
        distances["缓行"] + distances["拥堵"] + distances["严重拥堵"]
    ) / known_distance
    congested_ratio = (distances["拥堵"] + distances["严重拥堵"]) / known_distance
    if distances["严重拥堵"] > 0 or congested_ratio >= 0.2:
        level = "high"
    elif slow_ratio >= 0.1:
        level = "medium"
    else:
        level = "low"

    summary = "高德路况分段：" + "、".join(
        f"{name}{round(distance / 1000, 1)}km"
        for name, distance in distances.items()
        if distance > 0
    )
    return level, summary
