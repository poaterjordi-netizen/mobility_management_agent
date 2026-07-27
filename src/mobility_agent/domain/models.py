from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RiskProfile(StrEnum):
    STANDARD = "standard"
    CAUTIOUS = "cautious"
    VERY_CAUTIOUS = "very_cautious"


class TripSourceType(StrEnum):
    MANUAL = "manual"
    TEXT = "text"
    ICS = "ics"
    IMAGE = "image"


class Coordinates(StrictModel):
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)


class TripInput(StrictModel):
    flight_number: str = Field(pattern=r"^[A-Z0-9]{2}\d{3,4}$")
    departure_airport: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    destination_airport: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )
    terminal: str = Field(default="待确认", min_length=1, max_length=12)
    scheduled_departure: datetime
    departure_place: str = Field(min_length=2, max_length=80)
    departure_coordinates: Coordinates | None = None
    checked_baggage: bool = False
    accessibility_assistance: bool = False
    risk_profile: RiskProfile = RiskProfile.CAUTIOUS
    live_data_consent: bool = False
    model_egress_consent: bool = False
    itinerary_source: Literal[
        "manual",
        "ctrip",
        "umetrip",
        "airline",
        "calendar",
        "other",
    ] = "manual"
    user_disruption_notes: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("flight_number", "departure_airport", "destination_airport", mode="before")
    @classmethod
    def normalize_uppercase(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("scheduled_departure")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_departure must include a timezone")
        return value

    @field_validator("user_disruption_notes")
    @classmethod
    def validate_notes(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item.strip()]
        if any(len(item) > 120 for item in normalized):
            raise ValueError("each disruption note must be 120 characters or fewer")
        return normalized


class TripParseRequest(StrictModel):
    source_type: Literal["text", "ics"]
    content: str = Field(min_length=3, max_length=50_000)
    departure_place: str = Field(default="待确认出发地", min_length=2, max_length=80)
    checked_baggage: bool = False
    risk_profile: RiskProfile = RiskProfile.CAUTIOUS


class TripCandidate(StrictModel):
    candidate_id: str
    source_type: TripSourceType
    source_summary: str
    itinerary_source: Literal[
        "manual",
        "ctrip",
        "umetrip",
        "airline",
        "calendar",
        "other",
    ]
    flight_number: str | None = None
    departure_airport: str | None = None
    destination_airport: str | None = None
    terminal: str | None = None
    scheduled_departure: datetime | None = None
    departure_place: str
    checked_baggage: bool
    risk_profile: RiskProfile
    field_confidence: dict[str, float]
    missing_fields: list[str]
    warnings: list[str]
    redactions_applied: list[str]
    needs_user_confirmation: Literal[True] = True


SourceType = Literal[
    "user_confirmed",
    "official_api",
    "official_public",
    "public_feed",
    "configured_rule",
    "synthetic_rule",
    "derived",
]
Completeness = Literal["complete", "partial", "unavailable"]
Freshness = Literal["fresh", "stale", "not_applicable"]


class SourceMetadata(StrictModel):
    source_id: str
    source_name: str
    source_type: SourceType
    observed_at: datetime
    fresh_until: datetime | None = None
    scope: str
    completeness: Completeness
    freshness: Freshness
    confidence: float = Field(ge=0, le=1)
    source_url: str | None = None
    license_note: str | None = None
    warnings: list[str] = Field(default_factory=list)


class FlightSnapshot(StrictModel):
    flight_number: str
    status: Literal["scheduled", "delayed", "cancelled", "unknown"]
    scheduled_departure: datetime
    estimated_departure: datetime | None = None
    terminal: str
    gate: str | None = None
    checkin_open_at: datetime
    checkin_close_at: datetime
    boarding_start_at: datetime
    boarding_close_at: datetime
    delay_probability: float = Field(ge=0, le=1)
    metadata: SourceMetadata


class AirportProcessSnapshot(StrictModel):
    airport: str
    terminal: str
    checkin_minutes: int = Field(ge=0, le=180)
    security_minutes: int = Field(ge=0, le=180)
    walking_minutes: int = Field(ge=0, le=120)
    gate_distance_meters: int | None = Field(default=None, ge=0, le=20_000)
    accessibility_extra_minutes: int = Field(default=0, ge=0, le=120)
    metadata: SourceMetadata


class RouteSnapshot(StrictModel):
    origin_label: str
    destination_label: str
    distance_km: float | None = Field(default=None, ge=0, le=2_000)
    p50_minutes: int = Field(ge=1, le=720)
    p90_minutes: int = Field(ge=1, le=900)
    pickup_minutes: int = Field(ge=0, le=120)
    congestion_level: Literal["low", "medium", "high", "unknown"]
    incident_delay_minutes: int = Field(default=0, ge=0, le=240)
    metadata: SourceMetadata


class WeatherSnapshot(StrictModel):
    summary: str
    severity: Literal["none", "minor", "moderate", "severe", "unknown"]
    precipitation_probability: int | None = Field(default=None, ge=0, le=100)
    wind_speed_kph: float | None = Field(default=None, ge=0, le=300)
    buffer_minutes: int = Field(ge=0, le=180)
    metadata: SourceMetadata


class FlightTelemetrySnapshot(StrictModel):
    callsign: str
    icao24: str
    state: Literal["airborne", "ground", "unknown"]
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    altitude_meters: float | None = Field(default=None, ge=-1_000, le=30_000)
    groundspeed_kph: float | None = Field(default=None, ge=0, le=2_000)
    track_degrees: float | None = Field(default=None, ge=0, le=360)
    last_contact_at: datetime
    metadata: SourceMetadata


class AviationWeatherSnapshot(StrictModel):
    station_icao: str
    raw_metar: str
    observed_at: datetime
    flight_category: Literal["VFR", "MVFR", "IFR", "LIFR", "UNKNOWN"]
    visibility_km: float | None = Field(default=None, ge=0, le=100)
    wind_speed_kph: float | None = Field(default=None, ge=0, le=300)
    temperature_c: float | None = Field(default=None, ge=-100, le=70)
    metadata: SourceMetadata


class DisruptionSignal(StrictModel):
    signal_id: str
    category: Literal["event", "construction", "closure", "accident", "social_signal"]
    label: str
    impact_start: datetime
    impact_end: datetime
    impact_minutes: int = Field(ge=0, le=240)
    route_intersection: Literal["confirmed", "possible", "unknown"]
    metadata: SourceMetadata


class JourneyContext(StrictModel):
    observed_at: datetime
    data_scope: Literal["synthetic", "mixed", "live"]
    flight: FlightSnapshot
    airport: AirportProcessSnapshot
    route: RouteSnapshot
    weather: WeatherSnapshot
    flight_telemetry: FlightTelemetrySnapshot | None = None
    aviation_weather: AviationWeatherSnapshot | None = None
    disruptions: list[DisruptionSignal]
    missing_sources: list[str]
    warnings: list[str]


class EvidenceItem(StrictModel):
    evidence_id: str
    label: str
    value: str
    source: str
    source_type: SourceType
    observed_at: datetime
    fresh_until: datetime | None = None
    confidence: float = Field(ge=0, le=1)
    status: Literal["confirmed", "live", "configured", "synthetic", "derived", "stale"]
    scope: str = ""
    completeness: Completeness = "complete"
    source_url: str | None = None


class DecisionComponent(StrictModel):
    key: str
    label: str
    minutes: int = Field(ge=0, le=900)
    evidence_ids: list[str]


class DepartureDecision(StrictModel):
    recommended_leave_at: datetime
    latest_reasonable_leave_at: datetime
    target_terminal_arrival: datetime
    boarding_start_at: datetime
    checkin_close_at: datetime
    scheduled_departure: datetime
    risk_level: Literal["low", "medium", "high"]
    confidence: Literal["low", "medium", "high"]
    confidence_window_minutes: int = Field(ge=0, le=240)
    components: list[DecisionComponent]
    binding_constraints: list[str]
    assumptions: list[str]
    missing_evidence: list[str]
    policy_version: str = "decision-policy-0.4.1"


class RuntimeBoundary(StrictModel):
    data_scope: Literal["synthetic", "mixed", "live"]
    provider: str
    model: str | None = None
    persistence: Literal["none", "ephemeral"]
    automatic_booking: Literal[False]
    reminder_delivery: Literal["preview_only", "configured"]


class DecisionResponse(StrictModel):
    trip: TripInput
    context: JourneyContext
    decision: DepartureDecision
    evidence: list[EvidenceItem]
    assistant_summary: str
    verified: bool
    runtime: RuntimeBoundary


class ReminderPreviewRequest(StrictModel):
    trip: TripInput
    decision: DepartureDecision
    lead_hours: int = Field(default=24, ge=1, le=168)


class ReminderPreview(StrictModel):
    reminder_id: str
    remind_at: datetime
    title: str
    message: str
    status: Literal["preview"]
    channel_options: list[Literal["calendar", "web_notification", "wechat_subscription"]]
    requires_user_consent: Literal[True] = True
    idempotency_key: str
    calendar_ics: str


class ActionProposalRequest(StrictModel):
    trip: TripInput
    decision: DepartureDecision
    action_type: Literal["open_map", "open_ride_hailing"]


class ActionProposal(StrictModel):
    proposal_id: str
    action_type: Literal["open_map", "open_ride_hailing"]
    status: Literal["awaiting_user_confirmation"]
    label: str
    parameters_preview: dict[str, str]
    deep_link: str
    fallback_url: str
    expires_at: datetime
    idempotency_key: str
    requires_payment: Literal[False] = False
    automatic_booking: Literal[False] = False


class AssistantQuestionRequest(StrictModel):
    question: str = Field(min_length=2, max_length=300)
    decision: DecisionResponse


class AssistantAnswer(StrictModel):
    answer: str
    cited_evidence_ids: list[str]
    provider: str
    evidence_only: Literal[True] = True


class SourceStatus(StrictModel):
    source_id: str
    label: str
    category: Literal["flight", "airport", "route", "weather", "events", "model", "ocr"]
    mode: Literal["synthetic", "configured", "available", "blocked", "unavailable"]
    freshness_minutes: int | None = None
    requires_secret: bool
    enabled: bool
    detail: str


class CapabilitiesResponse(StrictModel):
    service: str
    version: str
    data_scope: Literal["synthetic", "mixed", "live"]
    provider: str
    planned_model: str
    features: list[str]
    guarded_features: list[str]
    blocked_actions: list[str]
    sources: list[SourceStatus]


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str
    data_scope: Literal["synthetic", "mixed", "live"]


class PrivacyExport(StrictModel):
    generated_at: datetime
    persistence: Literal["none", "ephemeral"]
    stored_personal_data: list[Any]
    note: str


class DeleteResponse(StrictModel):
    deleted: Literal[True]
    scope: str
    note: str
