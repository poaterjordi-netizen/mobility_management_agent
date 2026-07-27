from __future__ import annotations

import unittest
from datetime import datetime

from mobility_agent.decision import DecisionEngine, DecisionVerifier
from mobility_agent.domain.models import TripInput


class DecisionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = DecisionEngine()
        self.observed_at = datetime.fromisoformat("2026-07-27T10:00:00+08:00")

    def test_cautious_checked_baggage_decision_is_deterministic(self) -> None:
        trip = TripInput(
            flight_number="CA1234",
            departure_airport="PEK",
            terminal="T3",
            scheduled_departure="2026-08-01T09:20:00+08:00",
            departure_place="合成出发地",
            checked_baggage=True,
            risk_profile="cautious",
        )

        decision, evidence = self.engine.compute(trip, observed_at=self.observed_at)

        self.assertEqual(decision.target_terminal_arrival.isoformat(), "2026-08-01T06:50:00+08:00")
        self.assertEqual(decision.recommended_leave_at.isoformat(), "2026-08-01T05:15:00+08:00")
        self.assertEqual([item.minutes for item in decision.components], [150, 70, 15, 10])
        self.assertEqual(len(evidence), 5)
        DecisionVerifier(self.engine).verify(
            trip,
            decision,
            observed_at=self.observed_at,
        )

    def test_more_cautious_profile_leaves_earlier(self) -> None:
        base = {
            "flight_number": "MU5678",
            "departure_airport": "PVG",
            "terminal": "T1",
            "scheduled_departure": "2026-08-03T14:00:00+08:00",
            "departure_place": "合成出发地",
            "checked_baggage": False,
        }
        standard, _ = self.engine.compute(
            TripInput(**base, risk_profile="standard"),
            observed_at=self.observed_at,
        )
        cautious, _ = self.engine.compute(
            TripInput(**base, risk_profile="very_cautious"),
            observed_at=self.observed_at,
        )
        self.assertLess(cautious.recommended_leave_at, standard.recommended_leave_at)

    def test_naive_departure_time_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            TripInput(
                flight_number="CA1234",
                departure_airport="PEK",
                terminal="T3",
                scheduled_departure="2026-08-01T09:20:00",
                departure_place="合成出发地",
            )


if __name__ == "__main__":
    unittest.main()
