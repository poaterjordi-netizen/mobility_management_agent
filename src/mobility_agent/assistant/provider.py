from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Protocol

from mobility_agent.domain.models import (
    DepartureDecision,
    EvidenceItem,
    JourneyContext,
    TripInput,
)


class LLMProvider(Protocol):
    provider_id: str
    model: str | None

    def synthesize(
        self,
        trip: TripInput,
        context: JourneyContext,
        decision: DepartureDecision,
        evidence: list[EvidenceItem],
    ) -> str: ...

    def answer(self, question: str, evidence: list[EvidenceItem]) -> str: ...


class FakeProvider:
    provider_id = "deterministic-template"
    model = None

    def synthesize(
        self,
        trip: TripInput,
        context: JourneyContext,
        decision: DepartureDecision,
        evidence: list[EvidenceItem],
    ) -> str:
        del evidence
        time_text = decision.recommended_leave_at.strftime("%H:%M")
        arrival_text = decision.target_terminal_arrival.strftime("%H:%M")
        baggage_text = "含托运行李" if trip.checked_baggage else "无托运行李"
        coverage = (
            "实时与规则数据混合"
            if context.data_scope == "mixed"
            else "实时来源"
            if context.data_scope == "live"
            else "版本化保守规则"
        )
        return (
            f"建议 {time_text} 从“{trip.departure_place}”出发，"
            f"目标 {arrival_text} 到达 {trip.departure_airport} {trip.terminal}。"
            f"当前按{baggage_text}、{trip.risk_profile.value}风险偏好计算，"
            f"使用{coverage}；请在出发前再次确认航站楼、登机口和道路状态。"
        )

    def answer(self, question: str, evidence: list[EvidenceItem]) -> str:
        lowered = question.lower()
        if any(token in lowered for token in ("为什么", "依据", "几点", "出发")):
            selected = evidence
        elif any(token in lowered for token in ("天气", "下雨", "风")):
            selected = [item for item in evidence if item.evidence_id == "ev-weather"]
        elif any(token in lowered for token in ("路", "堵", "交通", "事故", "活动", "施工")):
            selected = [
                item for item in evidence if item.evidence_id in {"ev-route", "ev-disruptions"}
            ]
        elif any(token in lowered for token in ("机场", "安检", "登机", "值机", "步行")):
            selected = [
                item for item in evidence if item.evidence_id in {"ev-flight", "ev-airport"}
            ]
        else:
            selected = evidence[:4]
        details = "；".join(f"{item.label}：{item.value}" for item in selected)
        return f"根据当前证据，{details}。未覆盖的信息不会由模型补写。"


class OpenAICompatibleProvider:
    """Responses API adapter restricted to derived evidence and explanations."""

    provider_id = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str = "medium",
        timeout: float = 45.0,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAI-compatible provider requires an API key")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.timeout = timeout

    def synthesize(
        self,
        trip: TripInput,
        context: JourneyContext,
        decision: DepartureDecision,
        evidence: list[EvidenceItem],
    ) -> str:
        del trip, context
        return self._request(
            instructions=(
                "你是出行建议解释器。只能解释给定的已核验证据和决定，"
                "不得修改任何时间、补写实时事实或建议自动付款。用两句简洁中文回答。"
            ),
            context={
                "decision": {
                    "recommended_leave_at": decision.recommended_leave_at.isoformat(),
                    "target_terminal_arrival": decision.target_terminal_arrival.isoformat(),
                    "risk_level": decision.risk_level,
                    "confidence": decision.confidence,
                    "components": [
                        {"label": item.label, "minutes": item.minutes}
                        for item in decision.components
                    ],
                },
                "evidence": self._minimal_evidence(evidence),
            },
        )

    def answer(self, question: str, evidence: list[EvidenceItem]) -> str:
        return self._request(
            instructions=(
                "你是证据受限的出行问答助手。只可使用输入 evidence，"
                "不得声称访问了实时系统，不得生成输入中没有的时间或事实。"
                "如果证据不足，明确说未覆盖。"
            ),
            context={
                "question": question,
                "evidence": self._minimal_evidence(evidence),
            },
        )

    @staticmethod
    def _minimal_evidence(evidence: list[EvidenceItem]) -> list[dict[str, Any]]:
        return [
            {
                "evidence_id": item.evidence_id,
                "label": item.label,
                "value": item.value,
                "source_type": item.source_type,
                "confidence": item.confidence,
                "status": item.status,
            }
            for item in evidence
        ]

    def _request(self, *, instructions: str, context: dict[str, Any]) -> str:
        body = {
            "model": self.model,
            "instructions": instructions,
            "input": json.dumps(context, ensure_ascii=False),
            "reasoning": {"effort": self.reasoning_effort},
            "store": False,
        }
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("language model request failed safely") from exc
        text = payload.get("output_text") if isinstance(payload, dict) else None
        if isinstance(text, str) and text.strip():
            return text.strip()
        chunks = []
        for item in payload.get("output", []) if isinstance(payload, dict) else []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if isinstance(part, dict) and part.get("type") == "output_text":
                    value = part.get("text")
                    if isinstance(value, str):
                        chunks.append(value)
        result = "".join(chunks).strip()
        if not result:
            raise RuntimeError("language model returned no explanation")
        return result
