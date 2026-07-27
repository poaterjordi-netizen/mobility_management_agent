const test = require("node:test")
const assert = require("node:assert/strict")

const { buildDecisionView } = require("../miniprogram/utils/decision-view")

test("builds a stable view from a verified decision response", () => {
  process.env.TZ = "Asia/Shanghai"
  const view = buildDecisionView({
    verified: true,
    trip: { flight_number: "CA1234" },
    context: {
      flight: { checkin_close_at: "2026-08-01T08:30:00+08:00" },
      route: {
        distance_km: 22.4,
        congestion_level: "low",
      },
    },
    evidence: [{ evidence_id: "one" }, { evidence_id: "two" }],
    decision: {
      recommended_leave_at: "2026-08-01T05:15:00+08:00",
      latest_reasonable_leave_at: "2026-08-01T05:52:00+08:00",
      target_terminal_arrival: "2026-08-01T06:50:00+08:00",
      scheduled_departure: "2026-08-01T09:20:00+08:00",
      confidence: "medium",
    },
  })
  assert.equal(view.leaveTime, "05:15")
  assert.equal(view.latestTime, "05:52")
  assert.equal(view.terminalTime, "06:50")
  assert.equal(view.departureTime, "09:20")
  assert.equal(view.checkinCloseTime, "08:30")
  assert.equal(view.verifiedLabel, "确定性核验通过")
  assert.equal(view.evidenceCount, 2)
  assert.equal(view.routeDetail, "22.4 km · 畅通")
})

test("returns null for malformed decision payloads", () => {
  assert.equal(buildDecisionView(null), null)
  assert.equal(buildDecisionView({ decision: {} }), null)
})
