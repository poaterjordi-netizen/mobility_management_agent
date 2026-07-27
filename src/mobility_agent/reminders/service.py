from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from mobility_agent.domain.models import DepartureDecision, ReminderPreview, TripInput


class ReminderService:
    def preview(
        self,
        trip: TripInput,
        decision: DepartureDecision,
        *,
        lead_hours: int = 24,
        now: datetime | None = None,
    ) -> ReminderPreview:
        current = now or datetime.now(UTC)
        remind_at = decision.recommended_leave_at - timedelta(hours=lead_hours)
        if remind_at <= current:
            remind_at = current + timedelta(minutes=5)
        fingerprint = (
            f"{trip.flight_number}:{decision.recommended_leave_at.isoformat()}:{lead_hours}"
        )
        key = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]
        title = f"{trip.flight_number} 行前提醒"
        message = (
            f"建议 {decision.recommended_leave_at:%H:%M} 从出发地前往 "
            f"{trip.departure_airport} {trip.terminal}，"
            f"目标 {decision.target_terminal_arrival:%H:%M} 到达。"
            "是否需要现在打开地图并查看叫车？"
        )
        return ReminderPreview(
            reminder_id=f"rem-{key[:12]}",
            remind_at=remind_at,
            title=title,
            message=message,
            status="preview",
            channel_options=["calendar", "web_notification", "wechat_subscription"],
            idempotency_key=f"reminder:{key}",
            calendar_ics=self._calendar_ics(
                uid=f"mobility-{key}@local",
                remind_at=remind_at,
                title=title,
                message=message,
            ),
        )

    @staticmethod
    def _calendar_ics(*, uid: str, remind_at: datetime, title: str, message: str) -> str:
        utc_start = remind_at.astimezone(UTC)
        utc_end = utc_start + timedelta(minutes=15)
        stamp = datetime.now(UTC)

        def ics_time(value: datetime) -> str:
            return value.strftime("%Y%m%dT%H%M%SZ")

        def escape(value: str) -> str:
            return (
                value.replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\n", "\\n")
            )

        return "\r\n".join(
            [
                "BEGIN:VCALENDAR",
                "VERSION:2.0",
                "PRODID:-//Mobility Management Agent//行前//CN",
                "CALSCALE:GREGORIAN",
                "METHOD:PUBLISH",
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{ics_time(stamp)}",
                f"DTSTART:{ics_time(utc_start)}",
                f"DTEND:{ics_time(utc_end)}",
                f"SUMMARY:{escape(title)}",
                f"DESCRIPTION:{escape(message)}",
                "BEGIN:VALARM",
                "TRIGGER:PT0M",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{escape(message)}",
                "END:VALARM",
                "END:VEVENT",
                "END:VCALENDAR",
                "",
            ]
        )
