from __future__ import annotations

from datetime import UTC, datetime

from mobility_agent.assistant.provider import FakeProvider, LLMProvider
from mobility_agent.decision import DecisionEngine, DecisionVerifier
from mobility_agent.domain.models import DecisionResponse, TripInput


class AssistantService:
    def __init__(
        self,
        *,
        engine: DecisionEngine | None = None,
        verifier: DecisionVerifier | None = None,
        provider: LLMProvider | None = None,
    ) -> None:
        self.engine = engine or DecisionEngine()
        self.verifier = verifier or DecisionVerifier(self.engine)
        self.provider = provider or FakeProvider()

    def preview(self, trip: TripInput) -> DecisionResponse:
        observed_at = datetime.now(UTC)
        decision, evidence = self.engine.compute(trip, observed_at=observed_at)
        self.verifier.verify(trip, decision, observed_at=observed_at)
        summary = self.provider.synthesize(trip, decision, evidence)
        return DecisionResponse(
            trip=trip,
            decision=decision,
            evidence=evidence,
            assistant_summary=summary,
            verified=True,
            runtime={
                "data_scope": "synthetic",
                "provider": "fake",
                "planned_model": "gpt-5.6-sol",
                "persistence": "none",
                "automatic_booking": False,
            },
        )
