from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from mobility_agent.domain.models import (
    DecisionComponent,
    DepartureDecision,
    EvidenceItem,
    RiskProfile,
    TripInput,
)


@dataclass(frozen=True)
class RiskParameters:
    traffic_extra_minutes: int
    pickup_minutes: int
    uncertainty_minutes: int
    risk_level: str


RISK_PARAMETERS = {
    RiskProfile.STANDARD: RiskParameters(0, 10, 5, "low"),
    RiskProfile.CAUTIOUS: RiskParameters(15, 15, 10, "medium"),
    RiskProfile.VERY_CAUTIOUS: RiskParameters(30, 20, 15, "high"),
}

AIRPORT_ROUTE_BASELINES = {
    "PEK": 55,
    "PKX": 75,
    "PVG": 65,
    "SHA": 50,
    "HGH": 55,
    "TNA": 50,
}


class DecisionEngine:
    """Pure, replayable synthetic decision policy.

    This baseline deliberately uses registered synthetic rules. Real map, flight,
    airport, and weather adapters can replace the evidence inputs without changing
    the decision contract.
    """

    policy_version = "synthetic-demo-1.0.0"

    def compute(
        self,
        trip: TripInput,
        *,
        observed_at: datetime | None = None,
    ) -> tuple[DepartureDecision, list[EvidenceItem]]:
        observed = observed_at or datetime.now(UTC)
        parameters = RISK_PARAMETERS[trip.risk_profile]
        airport_process_minutes = 150 if trip.checked_baggage else 120
        route_baseline = AIRPORT_ROUTE_BASELINES.get(trip.departure_airport, 60)
        traffic_minutes = route_baseline + parameters.traffic_extra_minutes

        target_terminal_arrival = trip.scheduled_departure - timedelta(
            minutes=airport_process_minutes
        )
        recommended_leave_at = target_terminal_arrival - timedelta(
            minutes=(
                traffic_minutes
                + parameters.pickup_minutes
                + parameters.uncertainty_minutes
            )
        )
        latest_reasonable_leave_at = target_terminal_arrival - timedelta(
            minutes=max(route_baseline - 5, 30) + 8
        )

        evidence = [
            EvidenceItem(
                evidence_id="ev-trip",
                label="已确认行程",
                value=(
                    f"{trip.flight_number} · {trip.departure_airport} "
                    f"{trip.terminal} · {trip.scheduled_departure:%m月%d日 %H:%M}"
                ),
                source="用户输入（演示）",
                source_type="user_confirmed",
                observed_at=observed,
                confidence=1.0,
                status="confirmed",
            ),
            EvidenceItem(
                evidence_id="ev-airport",
                label="机场流程预算",
                value=f"{airport_process_minutes} 分钟",
                source="合成机场规则 synthetic-demo-1.0.0",
                source_type="synthetic_rule",
                observed_at=observed,
                confidence=0.72,
                status="synthetic",
            ),
            EvidenceItem(
                evidence_id="ev-route",
                label="道路时间分位数",
                value=f"{traffic_minutes} 分钟",
                source="合成道路模型（待接高德）",
                source_type="synthetic_rule",
                observed_at=observed,
                fresh_until=observed + timedelta(minutes=30),
                confidence=0.68,
                status="synthetic",
            ),
            EvidenceItem(
                evidence_id="ev-pickup",
                label="叫车等待预算",
                value=f"{parameters.pickup_minutes} 分钟",
                source="风险偏好规则",
                source_type="derived",
                observed_at=observed,
                confidence=0.75,
                status="derived",
            ),
            EvidenceItem(
                evidence_id="ev-uncertainty",
                label="数据不确定性缓冲",
                value=f"{parameters.uncertainty_minutes} 分钟",
                source="风险偏好规则",
                source_type="derived",
                observed_at=observed,
                confidence=0.8,
                status="derived",
            ),
        ]

        components = [
            DecisionComponent(
                key="airport_process",
                label="机场流程",
                minutes=airport_process_minutes,
                evidence_ids=["ev-airport"],
            ),
            DecisionComponent(
                key="traffic",
                label="道路交通",
                minutes=traffic_minutes,
                evidence_ids=["ev-route"],
            ),
            DecisionComponent(
                key="pickup",
                label="叫车等待",
                minutes=parameters.pickup_minutes,
                evidence_ids=["ev-pickup"],
            ),
            DecisionComponent(
                key="uncertainty",
                label="不确定性",
                minutes=parameters.uncertainty_minutes,
                evidence_ids=["ev-uncertainty"],
            ),
        ]

        decision = DepartureDecision(
            recommended_leave_at=recommended_leave_at,
            latest_reasonable_leave_at=latest_reasonable_leave_at,
            target_terminal_arrival=target_terminal_arrival,
            scheduled_departure=trip.scheduled_departure,
            risk_level=parameters.risk_level,  # type: ignore[arg-type]
            confidence="medium",
            components=components,
            binding_constraints=[
                "国内航班合成机场流程规则",
                f"{trip.risk_profile.value} 风险偏好",
            ],
            assumptions=[
                "当前为合成数据演示，不代表实时航班、道路或机场状态。",
                "尚未执行网约车预约，任何外部动作都需要用户确认。",
            ],
        )
        return decision, evidence
