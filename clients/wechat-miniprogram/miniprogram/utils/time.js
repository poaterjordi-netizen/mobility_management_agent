function pad(value) {
  return String(value).padStart(2, "0")
}

function parseDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatTime(value) {
  const date = parseDate(value)
  if (!date) return "--:--"
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatDate(value) {
  const date = parseDate(value)
  if (!date) return "日期待确认"
  const weekday = ["日", "一", "二", "三", "四", "五", "六"][date.getDay()]
  return `${date.getMonth() + 1}月${date.getDate()}日 周${weekday}`
}

function localDateParts(value) {
  const match = String(value || "").match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/)
  if (!match) return { date: "", time: "" }
  return { date: match[1], time: match[2] }
}

function toChinaIso(date, time) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(date || ""))) return ""
  if (!/^\d{2}:\d{2}$/.test(String(time || ""))) return ""
  return `${date}T${time}:00+08:00`
}

function todayDate(now = new Date()) {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

module.exports = {
  formatDate,
  formatTime,
  localDateParts,
  pad,
  toChinaIso,
  todayDate,
}
