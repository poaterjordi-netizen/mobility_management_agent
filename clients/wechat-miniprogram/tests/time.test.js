const test = require("node:test")
const assert = require("node:assert/strict")

const {
  formatDate,
  formatTime,
  localDateParts,
  toChinaIso,
  todayDate,
} = require("../miniprogram/utils/time")

test("formats ISO timestamps for the user timezone", () => {
  process.env.TZ = "Asia/Shanghai"
  assert.equal(formatTime("2026-08-01T05:15:00+08:00"), "05:15")
  assert.equal(formatDate("2026-08-01T09:20:00+08:00"), "8月1日 周六")
})

test("returns safe placeholders for invalid timestamps", () => {
  assert.equal(formatTime("invalid"), "--:--")
  assert.equal(formatDate("invalid"), "日期待确认")
})

test("converts editable date and time without losing the configured timezone", () => {
  assert.deepEqual(localDateParts("2026-08-01T09:20:00+08:00"), {
    date: "2026-08-01",
    time: "09:20",
  })
  assert.equal(toChinaIso("2026-08-01", "09:20"), "2026-08-01T09:20:00+08:00")
  assert.equal(toChinaIso("bad", "09:20"), "")
  assert.equal(todayDate(new Date(2026, 6, 27, 12, 0, 0)), "2026-07-27")
})
