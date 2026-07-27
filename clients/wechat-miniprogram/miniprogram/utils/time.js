function pad(value) {
  return String(value).padStart(2, "0")
}

function formatTime(value) {
  const date = new Date(value)
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function formatDate(value) {
  const date = new Date(value)
  const weekday = ["日", "一", "二", "三", "四", "五", "六"][date.getDay()]
  return `${date.getMonth() + 1}月${date.getDate()}日 周${weekday}`
}

module.exports = { formatDate, formatTime }
