const { formatDate, formatTime } = require("./time")

function buildDecisionView(result) {
  if (!result || !result.decision || !result.trip) return null
  const telemetry = result.context && result.context.flight_telemetry
  const metar = result.context && result.context.aviation_weather
  return {
    leaveTime: formatTime(result.decision.recommended_leave_at),
    latestTime: formatTime(result.decision.latest_reasonable_leave_at),
    terminalTime: formatTime(result.decision.target_terminal_arrival),
    departureTime: formatTime(result.decision.scheduled_departure),
    checkinCloseTime: result.context && result.context.flight
      ? formatTime(result.context.flight.checkin_close_at)
      : "--:--",
    departureDate: formatDate(result.decision.scheduled_departure),
    verifiedLabel: result.verified ? "确定性核验通过" : "结果待核验",
    confidenceLabel: `置信度：${result.decision.confidence || "未知"}`,
    evidenceCount: Array.isArray(result.evidence) ? result.evidence.length : 0,
    telemetryLabel: telemetry
      ? `${telemetry.callsign} · ${telemetry.state}`
      : "",
    telemetryTime: telemetry ? formatTime(telemetry.last_contact_at) : "",
    metarLabel: metar ? `${metar.station_icao} · ${metar.flight_category}` : "",
    metarTime: metar ? formatTime(metar.observed_at) : "",
    sourceWarnings: result.context && Array.isArray(result.context.warnings)
      ? result.context.warnings
      : [],
  }
}

module.exports = { buildDecisionView }
