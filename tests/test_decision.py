from __future__ import annotations

import unittest
from datetime import datetime

from mobility_agent.actions import ActionService
from mobility_agent.api.settings import ApiSettings
from mobility_agent.decision import DecisionEngine, DecisionVerifier
from mobility_agent.domain.models import TripInput
from mobility_agent.integrations import JourneyContextBuilder
from mobility_agent.reminders import ReminderService


class DecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = ApiSettings(environment="test", ocr_command=None)
        self.builder = JourneyContextBuilder(self.settings)
        self.engine = DecisionEngine()
        self.observed_at = datetime.fromisoformat("2026-07-27T10:00:00+08:00")

    @staticmethod
    def trip(**overrides: object) -> TripInput:
        base: dict[str, object] = {
            "flight_number": "CA1234",
            "departure_airport": "PEK",
            "destination_airport": "SHA",
            "terminal": "T3",
            "scheduled_departure": "2026-08-01T09:20:00+08:00",
            "departure_place": "合成出发地",
            "checked_baggage": True,
            "risk_profile": "cautious",
        }
        base.update(overrides)
        return TripInput(**base)

    def compute(self, trip: TripInput):
        context = self.builder.build(trip, observed_at=self.observed_at)
        decision, evidence = self.engine.compute(trip, context)
        return context, decision, evidence

    def test_cautious_checked_baggage_decision_is_deterministic(self) -> None:
        trip = self.trip(user_disruption_notes=["机场高速施工"])
        context, decision, evidence = self.compute(trip)

        self.assertEqual(
            decision.target_terminal_arrival.isoformat(),
            "2026-08-01T07:20:00+08:00",
        )
        self.assertEqual(
            decision.recommended_leave_at.isoformat(),
            "2026-08-01T05:42:00+08:00",
        )
        self.assertEqual(
            [item.minutes for item in decision.components],
            [120, 70, 12, 0, 6, 10],
        )
        self.assertEqual(len(evidence), 8)
        DecisionVerifier(self.engine).verify(trip, context, decision)

    def test_more_cautious_profile_leaves_earlier(self) -> None:
        standard_trip = self.trip(risk_profile="standard", checked_baggage=False)
        cautious_trip = self.trip(risk_profile="very_cautious", checked_baggage=False)
        _, standard, _ = self.compute(standard_trip)
        _, cautious, _ = self.compute(cautious_trip)
        self.assertLess(cautious.recommended_leave_at, standard.recommended_leave_at)

    def test_accessibility_and_disruption_add_conservative_time(self) -> None:
        _, baseline, _ = self.compute(self.trip(user_disruption_notes=[]))
        context, assisted, _ = self.compute(
            self.trip(
                accessibility_assistance=True,
                user_disruption_notes=["大型活动", "道路封闭", "交通事故"],
            )
        )
        self.assertLess(assisted.recommended_leave_at, baseline.recommended_leave_at)
        disruption = next(item for item in assisted.components if item.key == "disruptions")
        self.assertEqual(disruption.minutes, 16)
        self.assertEqual(len(context.disruptions), 3)

    def test_verifier_detects_tampering(self) -> None:
        trip = self.trip()
        context, decision, _ = self.compute(trip)
        tampered = decision.model_copy(
            update={"recommended_leave_at": decision.recommended_leave_at.replace(minute=0)}
        )
        with self.assertRaisesRegex(ValueError, "deterministic verification"):
            DecisionVerifier(self.engine).verify(trip, context, tampered)

    def test_reminder_and_action_ids_are_stable(self) -> None:
        trip = self.trip()
        _, decision, _ = self.compute(trip)
        now = datetime.fromisoformat("2026-07-27T10:00:00+08:00")
        reminders = ReminderService()
        first = reminders.preview(trip, decision, now=now)
        second = reminders.preview(trip, decision, now=now)
        self.assertEqual(first.idempotency_key, second.idempotency_key)
        self.assertEqual(first.remind_at.isoformat(), "2026-07-31T05:48:00+08:00")
        self.assertIn("METHOD:PUBLISH", first.calendar_ics)

        actions = ActionService(self.settings.airport_registry_path)
        first_action = actions.propose(
            trip,
            decision,
            action_type="open_map",
            now=now,
        )
        second_action = actions.propose(
            trip,
            decision,
            action_type="open_map",
            now=now,
        )
        self.assertEqual(first_action.idempotency_key, second_action.idempotency_key)
        self.assertIn("北京首都国际机场", first_action.parameters_preview["目的地"])

    def test_naive_departure_time_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.trip(scheduled_departure="2026-08-01T09:20:00")

    def test_public_feed_evidence_is_labeled_live(self) -> None:
        trip = self.trip()
        context = self.builder.build(trip, observed_at=self.observed_at)
        public_weather = context.weather.model_copy(
            update={
                "metadata": context.weather.metadata.model_copy(
                    update={
                        "source_type": "public_feed",
                        "source_name": "公开天气测试源",
                    }
                )
            }
        )
        _, evidence = self.engine.compute(
            trip,
            context.model_copy(update={"weather": public_weather}),
        )
        weather = next(item for item in evidence if item.evidence_id == "ev-weather")
        self.assertEqual(weather.status, "live")


if __name__ == "__main__":
    unittest.main()
