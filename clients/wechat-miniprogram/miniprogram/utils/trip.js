const FLIGHT_PATTERN = /^[A-Z0-9]{2}\d{3,4}$/
const AIRPORT_PATTERN = /^[A-Z]{3}$/

const RISK_OPTIONS = [
  { label: "标准", value: "standard" },
  { label: "稳妥", value: "cautious" },
  { label: "非常稳妥", value: "very_cautious" },
]

function normalizeTrip(trip) {
  const source = trip || {}
  const coordinates = source.departure_coordinates
  const normalizedCoordinates = coordinates
    && Number.isFinite(Number(coordinates.longitude))
    && Number.isFinite(Number(coordinates.latitude))
    ? {
        longitude: Number(coordinates.longitude),
        latitude: Number(coordinates.latitude),
      }
    : null
  return {
    flight_number: String(source.flight_number || "").trim().toUpperCase(),
    departure_airport: String(source.departure_airport || "").trim().toUpperCase(),
    destination_airport: String(source.destination_airport || "").trim().toUpperCase() || null,
    terminal: String(source.terminal || "").trim(),
    scheduled_departure: String(source.scheduled_departure || "").trim(),
    departure_place: String(source.departure_place || "").trim(),
    departure_coordinates: normalizedCoordinates,
    checked_baggage: Boolean(source.checked_baggage),
    accessibility_assistance: Boolean(source.accessibility_assistance),
    risk_profile: RISK_OPTIONS.some((item) => item.value === source.risk_profile)
      ? source.risk_profile
      : "cautious",
    live_data_consent: Boolean(source.live_data_consent),
    model_egress_consent: Boolean(source.model_egress_consent),
    itinerary_source: [
      "manual",
      "ctrip",
      "umetrip",
      "airline",
      "calendar",
      "other",
    ].includes(source.itinerary_source)
      ? source.itinerary_source
      : "manual",
    user_disruption_notes: Array.isArray(source.user_disruption_notes)
      ? source.user_disruption_notes
        .map((item) => String(item).trim())
        .filter(Boolean)
        .slice(0, 5)
      : [],
  }
}

function validateTrip(trip) {
  const value = normalizeTrip(trip)
  if (!FLIGHT_PATTERN.test(value.flight_number)) {
    return { valid: false, message: "请输入正确的航班号，例如 CA1234" }
  }
  if (!AIRPORT_PATTERN.test(value.departure_airport)) {
    return { valid: false, message: "出发机场需使用三个英文字母，例如 PEK" }
  }
  if (value.destination_airport && !AIRPORT_PATTERN.test(value.destination_airport)) {
    return { valid: false, message: "目的机场需使用三个英文字母，例如 SHA" }
  }
  if (!value.terminal || value.terminal.length > 12) {
    return { valid: false, message: "请填写不超过 12 个字符的航站楼" }
  }
  if (!value.scheduled_departure || Number.isNaN(new Date(value.scheduled_departure).getTime())) {
    return { valid: false, message: "请选择有效的计划起飞日期和时间" }
  }
  if (value.departure_place.length < 2 || value.departure_place.length > 80) {
    return { valid: false, message: "出发地需为 2–80 个字符" }
  }
  if (
    value.departure_coordinates
    && (
      value.departure_coordinates.longitude < -180
      || value.departure_coordinates.longitude > 180
      || value.departure_coordinates.latitude < -90
      || value.departure_coordinates.latitude > 90
    )
  ) {
    return { valid: false, message: "出发地经纬度超出有效范围" }
  }
  return { valid: true, message: "", trip: value }
}

function riskIndexFor(value) {
  const index = RISK_OPTIONS.findIndex((item) => item.value === value)
  return index < 0 ? 1 : index
}

module.exports = {
  AIRPORT_PATTERN,
  FLIGHT_PATTERN,
  RISK_OPTIONS,
  normalizeTrip,
  riskIndexFor,
  validateTrip,
}
