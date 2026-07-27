from __future__ import annotations

import unittest
from datetime import datetime

from mobility_agent.api.settings import ApiSettings
from mobility_agent.domain.models import RiskProfile, TripSourceType
from mobility_agent.intake import TripParser, redact_sensitive_text


class IntakeAndSettingsTests(unittest.TestCase):
    def test_text_parser_handles_year_rollover_and_missing_fields(self) -> None:
        candidate = TripParser().parse(
            "CA1832 杭州萧山机场 T4 8月1日 09:20",
            source_type=TripSourceType.TEXT,
            departure_place="杭州市滨江区",
            checked_baggage=False,
            risk_profile=RiskProfile.STANDARD,
            now=datetime.fromisoformat("2026-08-02T10:00:00+08:00"),
        )
        self.assertEqual(candidate.scheduled_departure.year, 2027)
        self.assertIn("目的机场", candidate.warnings[0])
        self.assertTrue(candidate.needs_user_confirmation)

    def test_redactor_removes_sensitive_values(self) -> None:
        original = "乘机人 张三，手机号 13800138000，邮箱 test@example.com，票号 1234567890"
        redacted, applied = redact_sensitive_text(original)
        self.assertNotIn("13800138000", redacted)
        self.assertNotIn("test@example.com", redacted)
        self.assertNotIn("张三", redacted)
        self.assertGreaterEqual(len(applied), 3)

    def test_settings_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "MOBILITY_DATA_MODE"):
            ApiSettings.from_env({"MOBILITY_DATA_MODE": "guess"})
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            ApiSettings.from_env({"MOBILITY_ASSISTANT_PROVIDER": "openai"})
        with self.assertRaisesRegex(ValueError, "must use HTTPS"):
            ApiSettings.from_env({"MOBILITY_FLIGHT_API_BASE": "http://example.test"})

    def test_environment_parsing_enables_only_explicit_flags(self) -> None:
        settings = ApiSettings.from_env(
            {
                "MOBILITY_DATA_MODE": "mixed",
                "MOBILITY_PUBLIC_DATA_ENABLED": "true",
                "MOBILITY_PERSONAL_DATA_ENABLED": "false",
                "MOBILITY_API_CORS_ORIGINS": "https://one.example, https://two.example",
                "MOBILITY_OCR_COMMAND": "/bin/false",
            }
        )
        self.assertEqual(settings.data_mode, "mixed")
        self.assertTrue(settings.public_data_enabled)
        self.assertFalse(settings.personal_data_enabled)
        self.assertEqual(len(settings.cors_origins), 2)
        self.assertEqual(settings.ocr_command, "/bin/false")


if __name__ == "__main__":
    unittest.main()
