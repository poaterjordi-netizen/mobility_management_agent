from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from mobility_agent.api.app import create_app
from mobility_agent.api.settings import ApiSettings


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(ApiSettings(environment="test")))

    def test_health_and_capabilities(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["data_scope"], "synthetic")
        self.assertEqual(health.headers["cache-control"], "no-store")

        capabilities = self.client.get("/api/v1/capabilities")
        self.assertEqual(capabilities.status_code, 200)
        self.assertEqual(capabilities.json()["provider"], "fake")
        self.assertIn("自动预约或付款", capabilities.json()["blocked_actions"])

    def test_demo_decision_preview(self) -> None:
        trip = self.client.get("/api/v1/demo/trip").json()
        response = self.client.post("/api/v1/decisions/preview", json=trip)
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["verified"])
        self.assertEqual(payload["runtime"]["persistence"], "none")
        self.assertEqual(response.headers["x-mobility-data-scope"], "synthetic")

    def test_unknown_fields_fail_closed(self) -> None:
        trip = self.client.get("/api/v1/demo/trip").json()
        trip["third_party_password"] = "must-not-be-accepted"
        response = self.client.post("/api/v1/decisions/preview", json=trip)
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
