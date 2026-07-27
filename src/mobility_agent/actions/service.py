from __future__ import annotations

import hashlib
import json
import urllib.parse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from mobility_agent.domain.models import ActionProposal, DepartureDecision, TripInput


class ActionService:
    def __init__(self, airport_registry_path: Path) -> None:
        payload = json.loads(airport_registry_path.read_text(encoding="utf-8"))
        self.airports: dict[str, dict[str, Any]] = payload["airports"]

    def propose(
        self,
        trip: TripInput,
        decision: DepartureDecision,
        *,
        action_type: str,
        now: datetime | None = None,
    ) -> ActionProposal:
        if action_type not in {"open_map", "open_ride_hailing"}:
            raise ValueError("unsupported action type")
        airport = self.airports.get(trip.departure_airport)
        destination_name = (
            f"{airport['name']} {trip.terminal}"
            if airport
            else f"{trip.departure_airport} 机场 {trip.terminal}"
        )
        destination = ""
        if airport:
            coordinates = airport["coordinates"]
            destination = f"{coordinates['longitude']},{coordinates['latitude']},{destination_name}"
        origin = ""
        if trip.departure_coordinates:
            origin = (
                f"{trip.departure_coordinates.longitude},"
                f"{trip.departure_coordinates.latitude},出发地"
            )
        query = urllib.parse.urlencode(
            {
                "from": origin,
                "to": destination,
                "mode": "car",
                "policy": "1",
                "src": "mobility-management-agent",
                "coordinate": "gaode",
                "callnative": "1",
            }
        )
        deep_link = f"https://uri.amap.com/navigation?{query}"
        fallback_query = urllib.parse.urlencode(
            {
                "keyword": destination_name,
                "city": airport.get("city", "") if airport else "",
                "src": "mobility-management-agent",
                "callnative": "1",
            }
        )
        fallback = f"https://uri.amap.com/search?{fallback_query}"
        current = now or datetime.now(UTC)
        fingerprint = hashlib.sha256(
            (
                f"{action_type}:{trip.flight_number}:{decision.recommended_leave_at.isoformat()}"
            ).encode()
        ).hexdigest()[:24]
        return ActionProposal(
            proposal_id=f"act-{fingerprint[:12]}",
            action_type=action_type,
            status="awaiting_user_confirmation",
            label=(
                "打开地图并查看叫车" if action_type == "open_ride_hailing" else "打开地图查看路线"
            ),
            parameters_preview={
                "出发时间": decision.recommended_leave_at.strftime("%m月%d日 %H:%M"),
                "出发地": trip.departure_place,
                "目的地": destination_name,
                "说明": "仅打开官方地图页面，不自动下单或付款",
            },
            deep_link=deep_link,
            fallback_url=fallback,
            expires_at=min(
                decision.recommended_leave_at,
                current + timedelta(days=7),
            ),
            idempotency_key=f"action:{fingerprint}",
        )
