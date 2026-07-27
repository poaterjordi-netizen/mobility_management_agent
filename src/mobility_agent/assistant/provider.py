from __future__ import annotations

from typing import Protocol

from mobility_agent.domain.models import DepartureDecision, EvidenceItem, TripInput


class LLMProvider(Protocol):
    provider_id: str

    def synthesize(
        self,
        trip: TripInput,
        decision: DepartureDecision,
        evidence: list[EvidenceItem],
    ) -> str: ...


class FakeProvider:
    provider_id = "fake"

    def synthesize(
        self,
        trip: TripInput,
        decision: DepartureDecision,
        evidence: list[EvidenceItem],
    ) -> str:
        del evidence
        time_text = decision.recommended_leave_at.strftime("%H:%M")
        arrival_text = decision.target_terminal_arrival.strftime("%H:%M")
        baggage_text = "含托运行李流程" if trip.checked_baggage else "按无托运行李流程"
        return (
            f"建议 {time_text} 从“{trip.departure_place}”出发，"
            f"目标 {arrival_text} 到达 {trip.departure_airport} {trip.terminal}。"
            f"{baggage_text}，当前结论使用合成规则，仅用于验证框架。"
        )
