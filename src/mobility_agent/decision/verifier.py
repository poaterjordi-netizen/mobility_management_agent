from __future__ import annotations

from datetime import datetime

from mobility_agent.decision.engine import DecisionEngine
from mobility_agent.domain.models import DepartureDecision, TripInput


class DecisionVerifier:
    def __init__(self, engine: DecisionEngine | None = None) -> None:
        self.engine = engine or DecisionEngine()

    def verify(
        self,
        trip: TripInput,
        decision: DepartureDecision,
        *,
        observed_at: datetime,
    ) -> None:
        expected, evidence = self.engine.compute(trip, observed_at=observed_at)
        if decision != expected:
            raise ValueError("departure decision failed deterministic verification")

        evidence_ids = {item.evidence_id for item in evidence}
        referenced_ids = {
            evidence_id
            for component in decision.components
            for evidence_id in component.evidence_ids
        }
        if not referenced_ids.issubset(evidence_ids):
            raise ValueError("decision references missing evidence")
        if not (
            decision.recommended_leave_at
            < decision.target_terminal_arrival
            < decision.scheduled_departure
        ):
            raise ValueError("decision timeline is not ordered")
