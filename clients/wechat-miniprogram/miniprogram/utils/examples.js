const BJTU_DUT_INTAKE = "【携程公开时刻测试】CA8908 北京首都国际机场 T3 → 大连周水子国际机场，2026/7/27 21:50 起飞。"

const BJTU_DUT_TRIP = {
  flight_number: "CA8908",
  departure_airport: "PEK",
  destination_airport: "DLC",
  terminal: "T3",
  scheduled_departure: "2026-07-27T21:50:00+08:00",
  departure_place: "北京交通大学（海淀校区）",
  departure_coordinates: {
    longitude: 116.342757,
    latitude: 39.952311,
  },
  checked_baggage: true,
  accessibility_assistance: false,
  risk_profile: "cautious",
  live_data_consent: true,
  model_egress_consent: false,
  itinerary_source: "ctrip",
  user_disruption_notes: [],
}

const BJTU_DUT_LAST_MILE = {
  scheduled_arrival: "23:05",
  pickup_window: "23:47–00:02",
  campus_arrival_window: "00:43–00:58",
  amap_url: "https://uri.amap.com/navigation?from=121.542585%2C38.964154%2C%E5%A4%A7%E8%BF%9E%E5%91%A8%E6%B0%B4%E5%AD%90%E5%9B%BD%E9%99%85%E6%9C%BA%E5%9C%BA&to=121.525200%2C38.883283%2C%E5%A4%A7%E8%BF%9E%E7%90%86%E5%B7%A5%E5%A4%A7%E5%AD%A6%E5%87%8C%E6%B0%B4%E6%A0%A1%E5%8C%BA&mode=car&policy=1&src=mobility-management-agent&coordinate=gaode&callnative=1",
}

function buildBjtuDutTrip() {
  return {
    ...BJTU_DUT_TRIP,
    departure_coordinates: { ...BJTU_DUT_TRIP.departure_coordinates },
    user_disruption_notes: [],
  }
}

module.exports = {
  BJTU_DUT_INTAKE,
  BJTU_DUT_LAST_MILE,
  buildBjtuDutTrip,
}
