const test = require("node:test")
const assert = require("node:assert/strict")

const {
  RISK_OPTIONS,
  normalizeTrip,
  riskIndexFor,
  validateTrip,
} = require("../miniprogram/utils/trip")

const validTrip = {
  flight_number: "ca1234",
  departure_airport: "pek",
  destination_airport: "sha",
  terminal: "T3",
  scheduled_departure: "2026-08-01T09:20:00+08:00",
  departure_place: "北京市朝阳区望京（合成示例）",
  checked_baggage: true,
  risk_profile: "cautious",
  departure_coordinates: { longitude: 116.4, latitude: 39.9 },
  accessibility_assistance: true,
  live_data_consent: true,
  model_egress_consent: false,
  user_disruption_notes: ["道路施工"],
  itinerary_source: "ctrip",
}

test("normalizes and validates a complete synthetic trip", () => {
  const validation = validateTrip(validTrip)
  assert.equal(validation.valid, true)
  assert.equal(validation.trip.flight_number, "CA1234")
  assert.equal(validation.trip.departure_airport, "PEK")
  assert.equal(validation.trip.destination_airport, "SHA")
  assert.deepEqual(validation.trip.departure_coordinates, {
    longitude: 116.4,
    latitude: 39.9,
  })
  assert.equal(validation.trip.user_disruption_notes.length, 1)
  assert.equal(validation.trip.itinerary_source, "ctrip")
})

test("rejects invalid decision inputs before network transmission", () => {
  assert.match(
    validateTrip({ ...validTrip, flight_number: "123" }).message,
    /航班号/,
  )
  assert.match(
    validateTrip({ ...validTrip, departure_airport: "北京" }).message,
    /三个英文字母/,
  )
  assert.match(
    validateTrip({ ...validTrip, destination_airport: "上海" }).message,
    /目的机场/,
  )
  assert.match(
    validateTrip({ ...validTrip, scheduled_departure: "" }).message,
    /日期和时间/,
  )
  assert.match(
    validateTrip({ ...validTrip, departure_place: "A" }).message,
    /2–80/,
  )
})

test("falls back to cautious risk without changing the allowed registry", () => {
  const normalized = normalizeTrip({ ...validTrip, risk_profile: "unknown" })
  assert.equal(normalized.risk_profile, "cautious")
  assert.equal(riskIndexFor("unknown"), 1)
  assert.deepEqual(RISK_OPTIONS.map((item) => item.value), [
    "standard",
    "cautious",
    "very_cautious",
  ])
})
