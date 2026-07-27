from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RiskProfile(StrEnum):
    STANDARD = "standard"
    CAUTIOUS = "cautious"
    VERY_CAUTIOUS = "very_cautious"


class TripInput(StrictModel):
    flight_number: str = Field(pattern=r"^[A-Z0-9]{2}\d{3,4}$")
    departure_airport: str = Field(min_length=3, max_length=3)
    terminal: str = Field(default="待确认", min_length=1, max_length=12)
    scheduled_departure: datetime
    departure_place: str = Field(min_length=2, max_length=80)
    checked_baggage: bool = False
    risk_profile: RiskProfile = RiskProfile.CAUTIOUS

    @field_validator("flight_number", "departure_airport", mode="before")
    @classmethod
    def normalize_uppercase(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("scheduled_departure")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("scheduled_departure must include a timezone")
        return value


class EvidenceItem(StrictModel):
    evidence_id: str
    label: str
    value: str
    source: str
    source_type: Literal["user_confirmed", "synthetic_rule", "derived"]
    observed_at: datetime
    fresh_until: datetime | None = None
    confidence: float = Field(ge=0, le=1)
    status: Literal["confirmed", "synthetic", "derived"]


class DecisionComponent(StrictModel):
    key: str
    label: str
    minutes: int = Field(ge=0, le=360)
    evidence_ids: list[str]


class DepartureDecision(StrictModel):
    recommended_leave_at: datetime
    latest_reasonable_leave_at: datetime
    target_terminal_arrival: datetime
    scheduled_departure: datetime
    risk_level: Literal["low", "medium", "high"]
    confidence: Literal["low", "medium", "high"]
    components: list[DecisionComponent]
    binding_constraints: list[str]
    assumptions: list[str]
    policy_version: Literal["synthetic-demo-1.0.0"] = "synthetic-demo-1.0.0"


class RuntimeBoundary(StrictModel):
    data_scope: Literal["synthetic"]
    provider: Literal["fake"]
    planned_model: Literal["gpt-5.6-sol"]
    persistence: Literal["none"]
    automatic_booking: Literal[False]


class DecisionResponse(StrictModel):
    trip: TripInput
    decision: DepartureDecision
    evidence: list[EvidenceItem]
    assistant_summary: str
    verified: bool
    runtime: RuntimeBoundary


class CapabilitiesResponse(StrictModel):
    service: str
    version: str
    data_scope: Literal["synthetic"]
    provider: Literal["fake"]
    planned_model: Literal["gpt-5.6-sol"]
    features: list[str]
    blocked_actions: list[str]


class HealthResponse(StrictModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str
    data_scope: Literal["synthetic"]
