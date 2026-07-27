const test = require("node:test")
const assert = require("node:assert/strict")

const {
  BJTU_DUT_INTAKE,
  BJTU_DUT_LAST_MILE,
  buildBjtuDutTrip,
} = require("../miniprogram/utils/examples")
const documentedRequest = require("../../../docs/examples/bjtu_pek_ca8908_evening_request.json")

test("北京交大到大连理工示例包含完整航段和真实起点", () => {
  const trip = buildBjtuDutTrip()

  assert.deepEqual(trip, documentedRequest)
  assert.equal(trip.flight_number, "CA8908")
  assert.equal(trip.departure_airport, "PEK")
  assert.equal(trip.destination_airport, "DLC")
  assert.equal(trip.terminal, "T3")
  assert.equal(trip.departure_place, "北京交通大学（海淀校区）")
  assert.deepEqual(trip.departure_coordinates, {
    longitude: 116.342757,
    latitude: 39.952311,
  })
  assert.match(BJTU_DUT_INTAKE, /21:50/)
})

test("示例构造器不会在重复载入时共享可变字段", () => {
  const first = buildBjtuDutTrip()
  const second = buildBjtuDutTrip()

  first.departure_coordinates.longitude = 0
  first.user_disruption_notes.push("测试")

  assert.equal(second.departure_coordinates.longitude, 116.342757)
  assert.deepEqual(second.user_disruption_notes, [])
})

test("大连落地段包含到校时间和高德路线", () => {
  assert.equal(BJTU_DUT_LAST_MILE.scheduled_arrival, "23:05")
  assert.equal(BJTU_DUT_LAST_MILE.pickup_window, "23:47–00:02")
  assert.equal(BJTU_DUT_LAST_MILE.campus_arrival_window, "00:43–00:58")
  assert.match(BJTU_DUT_LAST_MILE.amap_url, /^https:\/\/uri\.amap\.com\/navigation\?/)
})
