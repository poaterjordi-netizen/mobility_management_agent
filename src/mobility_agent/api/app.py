from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from mobility_agent import __version__
from mobility_agent.api.settings import ApiSettings
from mobility_agent.assistant import AssistantService
from mobility_agent.domain.models import (
    CapabilitiesResponse,
    DecisionResponse,
    HealthResponse,
    TripInput,
)


def demo_trip() -> TripInput:
    return TripInput(
        flight_number="CA1234",
        departure_airport="PEK",
        terminal="T3",
        scheduled_departure=datetime.fromisoformat("2026-08-01T09:20:00+08:00"),
        departure_place="北京市朝阳区望京（合成示例）",
        checked_baggage=True,
        risk_profile="cautious",
    )


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    runtime = settings or ApiSettings.from_env()
    application = FastAPI(
        title="Mobility Management Agent API",
        summary="Synthetic, governed airport-access decision framework",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.state.settings = runtime
    application.state.assistant = AssistantService()

    if runtime.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(runtime.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    @application.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": "mobility-management-agent",
            "docs": "/docs",
            "scope": "synthetic-framework",
        }

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "mobility-management-agent",
            "version": __version__,
            "environment": runtime.environment,
            "data_scope": "synthetic",
        }

    @application.get(
        "/api/v1/capabilities",
        response_model=CapabilitiesResponse,
        tags=["system"],
    )
    def capabilities() -> dict[str, object]:
        return {
            "service": "mobility-management-agent",
            "version": __version__,
            "data_scope": "synthetic",
            "provider": "fake",
            "planned_model": "gpt-5.6-sol",
            "features": [
                "行程字段确认",
                "确定性出发时刻计算",
                "证据卡片与核验",
                "Web 与微信小程序共享 API",
            ],
            "blocked_actions": [
                "读取其他 App 私有数据",
                "自动预约或付款",
                "使用合成结果冒充实时信息",
            ],
        }

    @application.get("/api/v1/demo/trip", response_model=TripInput, tags=["demo"])
    def get_demo_trip() -> TripInput:
        return demo_trip()

    @application.post(
        "/api/v1/decisions/preview",
        response_model=DecisionResponse,
        tags=["decisions"],
    )
    def preview_decision(trip: TripInput, response: Response) -> DecisionResponse:
        response.headers["X-Mobility-Data-Scope"] = "synthetic"
        return application.state.assistant.preview(trip)

    return application


app = create_app()
