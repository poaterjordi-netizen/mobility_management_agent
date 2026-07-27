from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from mobility_agent.api.app import create_app
from mobility_agent.api.settings import ApiSettings


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(ApiSettings(environment="test", ocr_command=None)))

    def test_health_capabilities_and_source_registry(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["data_scope"], "synthetic")
        self.assertEqual(health.json()["version"], "0.4.0")
        self.assertEqual(health.headers["cache-control"], "no-store")
        self.assertEqual(health.headers["x-frame-options"], "DENY")

        capabilities = self.client.get("/api/v1/capabilities")
        self.assertEqual(capabilities.status_code, 200)
        self.assertEqual(capabilities.json()["provider"], "deterministic-template")
        self.assertIn("自动付款、退改签或接受平台协议", capabilities.json()["blocked_actions"])
        self.assertIn("T-24 提醒预览与日历文件", capabilities.json()["features"])

        sources = self.client.get("/api/v1/sources")
        self.assertEqual(sources.status_code, 200)
        by_id = {item["source_id"]: item for item in sources.json()}
        self.assertFalse(by_id["flight-normalized-api"]["enabled"])
        self.assertFalse(by_id["adsb-lol-live"]["enabled"])
        self.assertEqual(by_id["aviationweather-metar"]["mode"], "blocked")
        self.assertEqual(by_id["local-tesseract"]["mode"], "unavailable")

    def test_demo_decision_preview_is_verified_and_evidence_complete(self) -> None:
        trip = self.client.get("/api/v1/demo/trip").json()
        response = self.client.post("/api/v1/decisions/preview", json=trip)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["verified"])
        self.assertEqual(payload["runtime"]["persistence"], "none")
        self.assertFalse(payload["runtime"]["automatic_booking"])
        self.assertEqual(response.headers["x-mobility-data-scope"], "synthetic")
        self.assertEqual(len(payload["evidence"]), 8)
        self.assertEqual(
            payload["decision"]["recommended_leave_at"],
            "2026-08-01T05:42:00+08:00",
        )
        evidence_ids = {item["evidence_id"] for item in payload["evidence"]}
        for component in payload["decision"]["components"]:
            self.assertTrue(set(component["evidence_ids"]).issubset(evidence_ids))

    def test_text_and_ics_intake_require_confirmation(self) -> None:
        text_response = self.client.post(
            "/api/v1/trips/candidates",
            json={
                "source_type": "text",
                "content": (
                    "【携程】CA1832 杭州萧山机场 T4 → 北京首都机场，"
                    "2026/8/1 09:20，手机 13800138000"
                ),
                "departure_place": "杭州市滨江区",
                "checked_baggage": True,
                "risk_profile": "cautious",
            },
        )
        self.assertEqual(text_response.status_code, 200)
        candidate = text_response.json()
        self.assertTrue(candidate["needs_user_confirmation"])
        self.assertEqual(candidate["flight_number"], "CA1832")
        self.assertEqual(candidate["itinerary_source"], "ctrip")
        self.assertEqual(candidate["departure_airport"], "HGH")
        self.assertEqual(candidate["destination_airport"], "PEK")
        self.assertEqual(candidate["terminal"], "T4")
        self.assertIn("手机号", candidate["redactions_applied"])

        ics_response = self.client.post(
            "/api/v1/trips/candidates",
            json={
                "source_type": "ics",
                "content": (
                    "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n"
                    "DTSTART;TZID=Asia/Shanghai:20260801T092000\r\n"
                    "SUMMARY:CA1832 杭州萧山机场至北京首都机场 T4\r\n"
                    "END:VEVENT\r\nEND:VCALENDAR\r\n"
                ),
                "departure_place": "杭州市滨江区",
            },
        )
        self.assertEqual(ics_response.status_code, 200)
        self.assertEqual(
            ics_response.json()["scheduled_departure"],
            "2026-08-01T09:20:00+08:00",
        )

    def test_image_intake_rejects_mime_signature_mismatch(self) -> None:
        response = self.client.post(
            "/api/v1/trips/candidates/image",
            files={"image": ("trip.png", b"not-a-png", "image/png")},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "本机 OCR 未配置")

        configured = TestClient(
            create_app(
                ApiSettings(
                    environment="test",
                    ocr_command="/bin/false",
                )
            )
        )
        invalid = configured.post(
            "/api/v1/trips/candidates/image",
            files={"image": ("trip.png", b"not-a-png", "image/png")},
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()["detail"], "PNG 文件签名无效")

    def test_reminder_action_question_and_privacy_workflow(self) -> None:
        trip = self.client.get("/api/v1/demo/trip").json()
        decision = self.client.post("/api/v1/decisions/preview", json=trip).json()

        reminder = self.client.post(
            "/api/v1/reminders/preview",
            json={
                "trip": trip,
                "decision": decision["decision"],
                "lead_hours": 24,
            },
        )
        self.assertEqual(reminder.status_code, 200)
        reminder_payload = reminder.json()
        self.assertEqual(reminder_payload["status"], "preview")
        self.assertIn("BEGIN:VCALENDAR", reminder_payload["calendar_ics"])
        self.assertIn("VALARM", reminder_payload["calendar_ics"])
        self.assertTrue(reminder_payload["requires_user_consent"])

        action = self.client.post(
            "/api/v1/action-proposals",
            json={
                "trip": trip,
                "decision": decision["decision"],
                "action_type": "open_ride_hailing",
            },
        )
        self.assertEqual(action.status_code, 200)
        action_payload = action.json()
        self.assertEqual(action_payload["status"], "awaiting_user_confirmation")
        self.assertTrue(action_payload["deep_link"].startswith("https://uri.amap.com/"))
        self.assertFalse(action_payload["automatic_booking"])
        self.assertFalse(action_payload["requires_payment"])

        answer = self.client.post(
            "/api/v1/assistant/questions",
            json={"question": "为什么这么早出发？", "decision": decision},
        )
        self.assertEqual(answer.status_code, 200)
        self.assertTrue(answer.json()["evidence_only"])
        self.assertGreater(len(answer.json()["cited_evidence_ids"]), 0)

        export = self.client.get("/api/v1/privacy/export")
        self.assertEqual(export.status_code, 200)
        self.assertEqual(export.json()["stored_personal_data"], [])
        deleted = self.client.delete("/api/v1/privacy/session")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["deleted"])

    def test_guarded_action_and_unknown_fields_fail_closed(self) -> None:
        guarded_client = TestClient(
            create_app(
                ApiSettings(
                    environment="test",
                    ride_hailing_actions_enabled=False,
                    ocr_command=None,
                )
            )
        )
        trip = guarded_client.get("/api/v1/demo/trip").json()
        decision = guarded_client.post("/api/v1/decisions/preview", json=trip).json()
        response = guarded_client.post(
            "/api/v1/action-proposals",
            json={
                "trip": trip,
                "decision": decision["decision"],
                "action_type": "open_ride_hailing",
            },
        )
        self.assertEqual(response.status_code, 403)

        trip["third_party_password"] = "must-not-be-accepted"
        response = self.client.post("/api/v1/decisions/preview", json=trip)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
