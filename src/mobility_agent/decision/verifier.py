from __future__ import annotations

from mobility_agent.decision.engine import DecisionEngine
from mobility_agent.domain.models import DepartureDecision, JourneyContext, TripInput


class DecisionVerifier:
    def __init__(self, engine: DecisionEngine | None = None) -> None:
        self.engine = engine or DecisionEngine()

    def verify(
        self,
        trip: TripInput,
        context: JourneyContext,
        decision: DepartureDecision,
    ) -> None:
        expected, evidence = self.engine.compute(trip, context)
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
        if not all(component.evidence_ids for component in decision.components):
            raise ValueError("each decision component must reference evidence")
        if not (
            decision.recommended_leave_at
            < decision.latest_reasonable_leave_at
            < decision.target_terminal_arrival
            < decision.scheduled_departure
        ):
            raise ValueError("decision timeline is not ordered")
        component_total = sum(
            component.minutes
            for component in decision.components
            if component.key != "airport_process"
        )
        expected_minutes = round(
            (decision.target_terminal_arrival - decision.recommended_leave_at).total_seconds() / 60
        )
        if component_total != expected_minutes:
            raise ValueError("departure components do not add up to the recommended leave time")
