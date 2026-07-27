from __future__ import annotations

from mobility_agent.api.settings import ApiSettings
from mobility_agent.assistant.provider import (
    FakeProvider,
    LLMProvider,
    OpenAICompatibleProvider,
)
from mobility_agent.decision import DecisionEngine, DecisionVerifier
from mobility_agent.domain.models import (
    AssistantAnswer,
    DecisionResponse,
    TripInput,
)
from mobility_agent.integrations import JourneyContextBuilder


class AssistantService:
    def __init__(
        self,
        settings: ApiSettings,
        *,
        engine: DecisionEngine | None = None,
        verifier: DecisionVerifier | None = None,
        provider: LLMProvider | None = None,
        context_builder: JourneyContextBuilder | None = None,
    ) -> None:
        self.settings = settings
        self.engine = engine or DecisionEngine()
        self.verifier = verifier or DecisionVerifier(self.engine)
        self.template_provider = FakeProvider()
        self.provider = provider or self._provider_from_settings(settings)
        self.context_builder = context_builder or JourneyContextBuilder(settings)

    def preview(self, trip: TripInput) -> DecisionResponse:
        context = self.context_builder.build(trip)
        decision, evidence = self.engine.compute(trip, context)
        self.verifier.verify(trip, context, decision)
        active_provider = self._active_provider(trip)
        try:
            summary = active_provider.synthesize(trip, context, decision, evidence)
        except RuntimeError:
            active_provider = self.template_provider
            summary = active_provider.synthesize(trip, context, decision, evidence)
        return DecisionResponse(
            trip=trip,
            context=context,
            decision=decision,
            evidence=evidence,
            assistant_summary=summary,
            verified=True,
            runtime={
                "data_scope": context.data_scope,
                "provider": active_provider.provider_id,
                "model": active_provider.model,
                "persistence": "none",
                "automatic_booking": False,
                "reminder_delivery": (
                    "configured" if self.settings.reminder_delivery_enabled else "preview_only"
                ),
            },
        )

    def answer(self, question: str, decision: DecisionResponse) -> AssistantAnswer:
        active_provider = self._active_provider(decision.trip)
        try:
            answer = active_provider.answer(question, decision.evidence)
        except RuntimeError:
            active_provider = self.template_provider
            answer = active_provider.answer(question, decision.evidence)
        cited = self._citations(question, decision)
        return AssistantAnswer(
            answer=answer,
            cited_evidence_ids=cited,
            provider=active_provider.provider_id,
        )

    def _active_provider(self, trip: TripInput) -> LLMProvider:
        if (
            isinstance(self.provider, OpenAICompatibleProvider)
            and trip.model_egress_consent
            and self.settings.model_evidence_egress == "derived-only"
        ):
            return self.provider
        return self.template_provider

    @staticmethod
    def _provider_from_settings(settings: ApiSettings) -> LLMProvider:
        if settings.assistant_provider == "openai":
            assert settings.openai_api_key
            return OpenAICompatibleProvider(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                model=settings.assistant_model,
                reasoning_effort=settings.assistant_reasoning_effort,
            )
        return FakeProvider()

    @staticmethod
    def _citations(question: str, decision: DecisionResponse) -> list[str]:
        lowered = question.lower()
        if any(token in lowered for token in ("天气", "下雨", "风")):
            return ["ev-weather"]
        if any(token in lowered for token in ("路", "堵", "交通", "事故", "活动", "施工")):
            return ["ev-route", "ev-disruptions"]
        if any(token in lowered for token in ("机场", "安检", "登机", "值机", "步行")):
            return ["ev-flight", "ev-airport"]
        return [item.evidence_id for item in decision.evidence]
