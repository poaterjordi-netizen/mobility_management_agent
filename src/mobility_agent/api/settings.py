from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DataMode = Literal["synthetic", "mixed", "live"]


def _bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_airport_registry() -> Path:
    candidates = (
        _repository_root() / "config" / "airports.json",
        Path.cwd() / "config" / "airports.json",
    )
    return next((path.resolve() for path in candidates if path.is_file()), candidates[0])


@dataclass(frozen=True)
class ApiSettings:
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: tuple[str, ...] = ()
    data_mode: DataMode = "synthetic"
    public_data_enabled: bool = False
    personal_data_enabled: bool = False
    amap_web_service_key: str | None = None
    flight_api_base: str | None = None
    flight_api_key: str | None = None
    assistant_provider: Literal["fake", "openai"] = "fake"
    assistant_model: str = "gpt-5.6-sol"
    assistant_reasoning_effort: str = "medium"
    model_intent_egress: Literal["deny", "redacted-only"] = "deny"
    model_evidence_egress: Literal["deny", "derived-only"] = "deny"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    ocr_command: str | None = None
    ocr_languages: str = "chi_sim+eng"
    reminder_delivery_enabled: bool = False
    wechat_subscription_template_id: str | None = None
    ride_hailing_actions_enabled: bool = True
    airport_registry_path: Path = _default_airport_registry()

    @classmethod
    def from_env(cls, environment: Mapping[str, str] | None = None) -> ApiSettings:
        env = os.environ if environment is None else environment
        origins = tuple(
            item.strip()
            for item in env.get("MOBILITY_API_CORS_ORIGINS", "").split(",")
            if item.strip()
        )
        data_mode = env.get("MOBILITY_DATA_MODE", "synthetic").strip().lower()
        if data_mode not in {"synthetic", "mixed", "live"}:
            raise ValueError("MOBILITY_DATA_MODE must be synthetic, mixed, or live")
        provider = env.get("MOBILITY_ASSISTANT_PROVIDER", "fake").strip().lower()
        if provider not in {"fake", "openai"}:
            raise ValueError("MOBILITY_ASSISTANT_PROVIDER must be fake or openai")
        intent_egress = env.get("MOBILITY_MODEL_INTENT_EGRESS", "deny").strip().lower()
        if intent_egress not in {"deny", "redacted-only"}:
            raise ValueError("MOBILITY_MODEL_INTENT_EGRESS must be deny or redacted-only")
        evidence_egress = env.get("MOBILITY_MODEL_EVIDENCE_EGRESS", "deny").strip().lower()
        if evidence_egress not in {"deny", "derived-only"}:
            raise ValueError("MOBILITY_MODEL_EVIDENCE_EGRESS must be deny or derived-only")
        openai_api_key = env.get("OPENAI_API_KEY", "").strip() or None
        if provider == "openai" and not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when MOBILITY_ASSISTANT_PROVIDER=openai")

        flight_api_base = env.get("MOBILITY_FLIGHT_API_BASE", "").strip() or None
        if flight_api_base and not flight_api_base.startswith("https://"):
            raise ValueError("MOBILITY_FLIGHT_API_BASE must use HTTPS")

        registry = env.get("MOBILITY_AIRPORT_REGISTRY_PATH", "").strip()
        configured_ocr = env.get("MOBILITY_OCR_COMMAND", "").strip() or None
        detected_ocr = configured_ocr or shutil.which("tesseract")
        return cls(
            environment=env.get("MOBILITY_ENV", "development").strip() or "development",
            host=env.get("MOBILITY_API_HOST", "127.0.0.1").strip() or "127.0.0.1",
            port=int(env.get("MOBILITY_API_PORT", "8000")),
            cors_origins=origins,
            data_mode=data_mode,  # type: ignore[arg-type]
            public_data_enabled=_bool(env.get("MOBILITY_PUBLIC_DATA_ENABLED")),
            personal_data_enabled=_bool(env.get("MOBILITY_PERSONAL_DATA_ENABLED")),
            amap_web_service_key=env.get("AMAP_WEB_SERVICE_KEY", "").strip() or None,
            flight_api_base=flight_api_base,
            flight_api_key=env.get("MOBILITY_FLIGHT_API_KEY", "").strip() or None,
            assistant_provider=provider,  # type: ignore[arg-type]
            assistant_model=(
                env.get("MOBILITY_ASSISTANT_MODEL", "gpt-5.6-sol").strip()
                or "gpt-5.6-sol"
            ),
            assistant_reasoning_effort=(
                env.get("MOBILITY_ASSISTANT_REASONING_EFFORT", "medium").strip() or "medium"
            ),
            model_intent_egress=intent_egress,  # type: ignore[arg-type]
            model_evidence_egress=evidence_egress,  # type: ignore[arg-type]
            openai_api_key=openai_api_key,
            openai_base_url=(
                env.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
                or "https://api.openai.com/v1"
            ),
            ocr_command=detected_ocr,
            ocr_languages=env.get("MOBILITY_OCR_LANGUAGES", "chi_sim+eng").strip()
            or "chi_sim+eng",
            reminder_delivery_enabled=_bool(env.get("MOBILITY_REMINDER_DELIVERY_ENABLED")),
            wechat_subscription_template_id=(
                env.get("MOBILITY_WECHAT_SUBSCRIPTION_TEMPLATE_ID", "").strip() or None
            ),
            ride_hailing_actions_enabled=_bool(
                env.get("MOBILITY_RIDE_HAILING_ACTIONS_ENABLED"),
                default=True,
            ),
            airport_registry_path=(
                Path(registry).expanduser().resolve()
                if registry
                else _default_airport_registry()
            ),
        )
