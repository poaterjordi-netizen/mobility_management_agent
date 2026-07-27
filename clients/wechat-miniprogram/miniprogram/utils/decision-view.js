const { formatDate, formatTime } = require("./time")

function buildDecisionView(result) {
  if (!result || !result.decision || !result.trip) return null
  return {
    leaveTime: formatTime(result.decision.recommended_leave_at),
    latestTime: formatTime(result.decision.latest_reasonable_leave_at),
    terminalTime: formatTime(result.decision.target_terminal_arrival),
    departureTime: formatTime(result.decision.scheduled_departure),
    departureDate: formatDate(result.decision.scheduled_departure),
    verifiedLabel: result.verified ? "确定性核验通过" : "结果待核验",
    confidenceLabel: `置信度：${result.decision.confidence || "未知"}`,
    evidenceCount: Array.isArray(result.evidence) ? result.evidence.length : 0,
  }
}

module.exports = { buildDecisionView }
