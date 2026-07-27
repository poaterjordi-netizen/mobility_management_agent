from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from mobility_agent import __version__
from mobility_agent.actions import ActionService
from mobility_agent.api.settings import ApiSettings
from mobility_agent.assistant import AssistantService
from mobility_agent.domain.models import (
    ActionProposal,
    ActionProposalRequest,
    AssistantAnswer,
    AssistantQuestionRequest,
    CapabilitiesResponse,
    DecisionResponse,
    DeleteResponse,
    HealthResponse,
    PrivacyExport,
    ReminderPreview,
    ReminderPreviewRequest,
    RiskProfile,
    SourceStatus,
    TripCandidate,
    TripInput,
    TripParseRequest,
    TripSourceType,
)
from mobility_agent.intake import LocalOCRService, TripParser
from mobility_agent.reminders import ReminderService


def demo_trip() -> TripInput:
    return TripInput(
        flight_number="CA1234",
        departure_airport="PEK",
        destination_airport="SHA",
        terminal="T3",
        scheduled_departure=datetime.fromisoformat("2026-08-01T09:20:00+08:00"),
        departure_place="北京市朝阳区望京（合成示例）",
        checked_baggage=True,
        risk_profile="cautious",
        user_disruption_notes=["机场高速施工演练（合成）"],
    )


def create_app(settings: ApiSettings | None = None) -> FastAPI:
    runtime = settings or ApiSettings.from_env()
    application = FastAPI(
        title="Mobility Management Agent API",
        summary="Governed, evidence-backed airport-access mobility concierge",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    application.state.settings = runtime
    application.state.assistant = AssistantService(runtime)
    application.state.trip_parser = TripParser()
    application.state.ocr = LocalOCRService(runtime.ocr_command, runtime.ocr_languages)
    application.state.reminders = ReminderService()
    application.state.actions = ActionService(runtime.airport_registry_path)

    if runtime.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(runtime.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["Content-Type"],
        )

    @application.middleware("http")
    async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

    @application.get("/", include_in_schema=False)
    def root() -> dict[str, str]:
        return {
            "service": "mobility-management-agent",
            "docs": "/docs",
            "scope": "governed-mobility-concierge",
            "version": __version__,
        }

    @application.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "mobility-management-agent",
            "version": __version__,
            "environment": runtime.environment,
            "data_scope": runtime.data_mode,
        }

    @application.get(
        "/api/v1/sources",
        response_model=list[SourceStatus],
        tags=["system"],
    )
    def sources() -> list[SourceStatus]:
        return application.state.assistant.context_builder.source_statuses()

    @application.get(
        "/api/v1/capabilities",
        response_model=CapabilitiesResponse,
        tags=["system"],
    )
    def capabilities() -> dict[str, object]:
        source_statuses = application.state.assistant.context_builder.source_statuses()
        return {
            "service": "mobility-management-agent",
            "version": __version__,
            "data_scope": runtime.data_mode,
            "provider": application.state.assistant.provider.provider_id,
            "planned_model": runtime.assistant_model,
            "features": [
                "手工、文本、ICS 与截图行程导入",
                "公开 ADS-B 航空器遥测与获权航班接口",
                "Open-Meteo 预报与 AviationWeather.gov METAR 实况",
                "机场/路线/官方交通通告上下文",
                "确定性出发时刻计算与完整重算核验",
                "证据受限解释与问答",
                "T-24 提醒预览与日历文件",
                "用户确认后的地图/叫车入口",
                "Web 与微信小程序共享 API",
                "隐私导出与删除语义",
            ],
            "guarded_features": [
                "实时高德路线需要服务端 Key、坐标和用户同意",
                "公开 ADS-B 仅在用户同意且航班临近时查询，不替代航司动态",
                "值机、登机口与航班计划仍需获权规范化 HTTPS 接口或用户确认",
                "模型解释需要运行时密钥、出域策略和用户同意",
                "微信订阅投递需要模板、AppSecret、用户授权和幂等 Outbox",
            ],
            "blocked_actions": [
                "逆向或抓取其他 App 私有数据",
                "绕过用户确认自动预约车辆",
                "自动付款、退改签或接受平台协议",
                "使用缺失或低可信事实生成精确时间",
            ],
            "sources": source_statuses,
        }

    @application.get("/api/v1/demo/trip", response_model=TripInput, tags=["demo"])
    def get_demo_trip() -> TripInput:
        return demo_trip()

    @application.post(
        "/api/v1/trips/candidates",
        response_model=TripCandidate,
        tags=["trips"],
    )
    def parse_trip_candidate(request: TripParseRequest) -> TripCandidate:
        return application.state.trip_parser.parse(
            request.content,
            source_type=TripSourceType(request.source_type),
            departure_place=request.departure_place,
            checked_baggage=request.checked_baggage,
            risk_profile=request.risk_profile,
        )

    @application.post(
        "/api/v1/trips/candidates/image",
        response_model=TripCandidate,
        tags=["trips"],
    )
    async def parse_trip_image(
        image: Annotated[UploadFile, File()],
        departure_place: Annotated[str, Form()] = "待确认出发地",
        checked_baggage: Annotated[bool, Form()] = False,
        risk_profile: Annotated[RiskProfile, Form()] = RiskProfile.CAUTIOUS,
    ) -> TripCandidate:
        content_type = image.content_type or ""
        payload = await image.read(application.state.ocr.max_bytes + 1)
        await image.close()
        try:
            text = application.state.ocr.extract(payload, content_type=content_type)
            return application.state.trip_parser.parse(
                text,
                source_type=TripSourceType.IMAGE,
                departure_place=departure_place,
                checked_baggage=checked_baggage,
                risk_profile=risk_profile,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @application.post(
        "/api/v1/decisions/preview",
        response_model=DecisionResponse,
        tags=["decisions"],
    )
    def preview_decision(trip: TripInput, response: Response) -> DecisionResponse:
        response.headers["X-Mobility-Data-Scope"] = runtime.data_mode
        try:
            return application.state.assistant.preview(trip)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post(
        "/api/v1/assistant/questions",
        response_model=AssistantAnswer,
        tags=["assistant"],
    )
    def answer_question(request: AssistantQuestionRequest) -> AssistantAnswer:
        return application.state.assistant.answer(request.question, request.decision)

    @application.post(
        "/api/v1/reminders/preview",
        response_model=ReminderPreview,
        tags=["reminders"],
    )
    def preview_reminder(request: ReminderPreviewRequest) -> ReminderPreview:
        return application.state.reminders.preview(
            request.trip,
            request.decision,
            lead_hours=request.lead_hours,
        )

    @application.post(
        "/api/v1/action-proposals",
        response_model=ActionProposal,
        tags=["actions"],
    )
    def propose_action(request: ActionProposalRequest) -> ActionProposal:
        if request.action_type == "open_ride_hailing" and not runtime.ride_hailing_actions_enabled:
            raise HTTPException(status_code=403, detail="地图/叫车入口当前未启用")
        try:
            return application.state.actions.propose(
                request.trip,
                request.decision,
                action_type=request.action_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.get(
        "/api/v1/privacy/export",
        response_model=PrivacyExport,
        tags=["privacy"],
    )
    def privacy_export() -> PrivacyExport:
        return PrivacyExport(
            generated_at=datetime.now(UTC),
            persistence="none",
            stored_personal_data=[],
            note="当前服务端不持久化行程、位置、OCR 图片或问答内容。",
        )

    @application.delete(
        "/api/v1/privacy/session",
        response_model=DeleteResponse,
        tags=["privacy"],
    )
    def delete_session() -> DeleteResponse:
        return DeleteResponse(
            deleted=True,
            scope="server-session",
            note="当前架构无服务端会话数据；客户端应同时清空运行内存。",
        )

    return application


app = create_app()
