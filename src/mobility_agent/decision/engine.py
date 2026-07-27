from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta

from mobility_agent.domain.models import (
    DecisionComponent,
    DepartureDecision,
    EvidenceItem,
    JourneyContext,
    RiskProfile,
    SourceMetadata,
    TripInput,
)


@dataclass(frozen=True)
class RiskParameters:
    uncertainty_minutes: int
    route_quantile: str
    confidence_window_minutes: int


RISK_PARAMETERS = {
    RiskProfile.STANDARD: RiskParameters(5, "p50", 12),
    RiskProfile.CAUTIOUS: RiskParameters(10, "p90", 20),
    RiskProfile.VERY_CAUTIOUS: RiskParameters(18, "p90-plus", 30),
}


class DecisionEngine:
    """Pure, replayable airport-access decision policy."""

    policy_version = "decision-policy-0.3.0"

    def compute(
        self,
        trip: TripInput,
        context: JourneyContext,
    ) -> tuple[DepartureDecision, list[EvidenceItem]]:
        if context.flight.status == "cancelled":
            raise ValueError("cancelled flight does not have an airport departure decision")

        parameters = RISK_PARAMETERS[trip.risk_profile]
        scheduled = context.flight.scheduled_departure
        airport = context.airport

        baseline_lead = 120 if trip.checked_baggage else 90
        if trip.accessibility_assistance:
            baseline_lead += 15
        checkin_constraint = context.flight.checkin_close_at - timedelta(
            minutes=airport.checkin_minutes + airport.accessibility_extra_minutes
        )
        boarding_constraint = context.flight.boarding_start_at - timedelta(
            minutes=(
                airport.security_minutes
                + airport.walking_minutes
                + airport.accessibility_extra_minutes
            )
        )
        baseline_constraint = scheduled - timedelta(minutes=baseline_lead)
        target_terminal_arrival = min(
            checkin_constraint,
            boarding_constraint,
            baseline_constraint,
        )
        airport_process_minutes = round(
            (scheduled - target_terminal_arrival).total_seconds() / 60
        )

        spread = max(context.route.p90_minutes - context.route.p50_minutes, 0)
        if parameters.route_quantile == "p50":
            route_minutes = context.route.p50_minutes
        elif parameters.route_quantile == "p90-plus":
            route_minutes = context.route.p90_minutes + max(8, math.ceil(spread / 2))
        else:
            route_minutes = context.route.p90_minutes

        disruption_minutes = min(
            30,
            sum(
                signal.impact_minutes
                if signal.route_intersection == "confirmed"
                else math.ceil(signal.impact_minutes / 2)
                if signal.route_intersection == "possible"
                else 0
                for signal in context.disruptions
            ),
        )
        weather_minutes = context.weather.buffer_minutes
        pickup_minutes = context.route.pickup_minutes
        uncertainty_minutes = parameters.uncertainty_minutes

        recommended_leave_at = target_terminal_arrival - timedelta(
            minutes=(
                route_minutes
                + pickup_minutes
                + weather_minutes
                + disruption_minutes
                + uncertainty_minutes
            )
        )
        latest_reasonable_leave_at = target_terminal_arrival - timedelta(
            minutes=context.route.p50_minutes + max(5, pickup_minutes // 2)
        )

        confidence_score = self._confidence(context)
        confidence = (
            "high" if confidence_score >= 0.85 else "medium" if confidence_score >= 0.62 else "low"
        )
        buffer_minutes = weather_minutes + disruption_minutes + uncertainty_minutes
        risk_level = "high" if buffer_minutes >= 35 else "medium" if buffer_minutes >= 15 else "low"

        evidence = self._evidence(
            trip,
            context,
            airport_process_minutes=airport_process_minutes,
            route_minutes=route_minutes,
            disruption_minutes=disruption_minutes,
            uncertainty_minutes=uncertainty_minutes,
        )
        components = [
            DecisionComponent(
                key="airport_process",
                label="机场流程与航班约束",
                minutes=airport_process_minutes,
                evidence_ids=["ev-flight", "ev-airport"],
            ),
            DecisionComponent(
                key="route",
                label=f"道路交通（{parameters.route_quantile.upper()}）",
                minutes=route_minutes,
                evidence_ids=["ev-route"],
            ),
            DecisionComponent(
                key="pickup",
                label="叫车等待",
                minutes=pickup_minutes,
                evidence_ids=["ev-pickup"],
            ),
            DecisionComponent(
                key="weather",
                label="天气缓冲",
                minutes=weather_minutes,
                evidence_ids=["ev-weather"],
            ),
            DecisionComponent(
                key="disruptions",
                label="活动/施工/事故缓冲",
                minutes=disruption_minutes,
                evidence_ids=["ev-disruptions"],
            ),
            DecisionComponent(
                key="uncertainty",
                label="不确定性缓冲",
                minutes=uncertainty_minutes,
                evidence_ids=["ev-uncertainty"],
            ),
        ]

        binding_constraints = [
            min(
                (
                    ("值机截止约束", checkin_constraint),
                    ("登机与步行约束", boarding_constraint),
                    ("最低提前到场约束", baseline_constraint),
                ),
                key=lambda item: item[1],
            )[0],
            f"{trip.risk_profile.value} 风险偏好 / {parameters.route_quantile}",
        ]
        assumptions = [
            "出发地到机场采用道路交通；未自动创建任何预约或付款。",
            "低可信事件只按可能影响计入有限缓冲，不作为确定事实。",
        ]
        if context.missing_sources:
            assumptions.append(
                "部分实时来源缺失，已使用版本化保守规则："
                + "、".join(context.missing_sources)
            )

        decision = DepartureDecision(
            recommended_leave_at=recommended_leave_at,
            latest_reasonable_leave_at=latest_reasonable_leave_at,
            target_terminal_arrival=target_terminal_arrival,
            boarding_start_at=context.flight.boarding_start_at,
            checkin_close_at=context.flight.checkin_close_at,
            scheduled_departure=scheduled,
            risk_level=risk_level,
            confidence=confidence,
            confidence_window_minutes=parameters.confidence_window_minutes,
            components=components,
            binding_constraints=binding_constraints,
            assumptions=assumptions,
            missing_evidence=context.missing_sources,
            policy_version=self.policy_version,
        )
        return decision, evidence

    @staticmethod
    def _confidence(context: JourneyContext) -> float:
        values = [
            context.flight.metadata.confidence,
            context.airport.metadata.confidence,
            context.route.metadata.confidence,
            context.weather.metadata.confidence,
        ]
        average = sum(values) / len(values)
        penalty = min(len(context.missing_sources) * 0.06, 0.24)
        return max(0.0, average - penalty)

    def _evidence(
        self,
        trip: TripInput,
        context: JourneyContext,
        *,
        airport_process_minutes: int,
        route_minutes: int,
        disruption_minutes: int,
        uncertainty_minutes: int,
    ) -> list[EvidenceItem]:
        observed = context.observed_at
        disruption_source = (
            "；".join(signal.metadata.source_name for signal in context.disruptions)
            if context.disruptions
            else "当前没有用户报告的事件信号"
        )
        return [
            EvidenceItem(
                evidence_id="ev-trip",
                label="已确认行程",
                value=(
                    f"{trip.flight_number} · {trip.departure_airport} "
                    f"{trip.terminal} · {trip.scheduled_departure:%m月%d日 %H:%M}"
                ),
                source="用户确认",
                source_type="user_confirmed",
                observed_at=observed,
                confidence=1.0,
                status="confirmed",
                scope="active-trip",
            ),
            self._from_metadata(
                evidence_id="ev-flight",
                label="航班时间窗",
                value=(
                    f"值机截止 {context.flight.checkin_close_at:%H:%M} · "
                    f"开始登机 {context.flight.boarding_start_at:%H:%M}"
                ),
                metadata=context.flight.metadata,
            ),
            self._from_metadata(
                evidence_id="ev-airport",
                label="机场流程预算",
                value=(
                    f"{airport_process_minutes} 分钟 · 安检 {context.airport.security_minutes} "
                    f"· 步行 {context.airport.walking_minutes}"
                ),
                metadata=context.airport.metadata,
            ),
            self._from_metadata(
                evidence_id="ev-route",
                label="道路时间分位数",
                value=(
                    f"采用 {route_minutes} 分钟 · "
                    f"P50 {context.route.p50_minutes} / P90 {context.route.p90_minutes}"
                ),
                metadata=context.route.metadata,
            ),
            EvidenceItem(
                evidence_id="ev-pickup",
                label="叫车等待预算",
                value=f"{context.route.pickup_minutes} 分钟",
                source="风险偏好与接驾规则",
                source_type="derived",
                observed_at=observed,
                confidence=0.78,
                status="derived",
                scope="pickup",
            ),
            self._from_metadata(
                evidence_id="ev-weather",
                label="天气",
                value=f"{context.weather.summary} · 缓冲 {context.weather.buffer_minutes} 分钟",
                metadata=context.weather.metadata,
            ),
            EvidenceItem(
                evidence_id="ev-disruptions",
                label="活动/施工/事故",
                value=f"{len(context.disruptions)} 条信号 · 缓冲 {disruption_minutes} 分钟",
                source=disruption_source,
                source_type=(
                    context.disruptions[0].metadata.source_type
                    if context.disruptions
                    else "derived"
                ),
                observed_at=observed,
                fresh_until=(
                    min(
                        (
                            signal.metadata.fresh_until
                            for signal in context.disruptions
                            if signal.metadata.fresh_until
                        ),
                        default=None,
                    )
                ),
                confidence=(
                    min(signal.metadata.confidence for signal in context.disruptions)
                    if context.disruptions
                    else 0.7
                ),
                status="derived",
                scope=f"{trip.departure_airport}:possible-route",
                completeness="partial" if context.disruptions else "complete",
            ),
            EvidenceItem(
                evidence_id="ev-uncertainty",
                label="数据不确定性缓冲",
                value=f"{uncertainty_minutes} 分钟",
                source=f"{trip.risk_profile.value} 风险策略",
                source_type="derived",
                observed_at=observed,
                confidence=0.85,
                status="derived",
                scope=self.policy_version,
            ),
        ]

    @staticmethod
    def _from_metadata(
        *,
        evidence_id: str,
        label: str,
        value: str,
        metadata: SourceMetadata,
    ) -> EvidenceItem:
        if metadata.freshness == "stale":
            status = "stale"
        elif metadata.source_type in {"official_api", "official_public"}:
            status = "live"
        elif metadata.source_type == "configured_rule":
            status = "configured"
        elif metadata.source_type == "user_confirmed":
            status = "confirmed"
        elif metadata.source_type == "derived":
            status = "derived"
        else:
            status = "synthetic"
        return EvidenceItem(
            evidence_id=evidence_id,
            label=label,
            value=value,
            source=metadata.source_name,
            source_type=metadata.source_type,
            observed_at=metadata.observed_at,
            fresh_until=metadata.fresh_until,
            confidence=metadata.confidence,
            status=status,
            scope=metadata.scope,
            completeness=metadata.completeness,
        )
