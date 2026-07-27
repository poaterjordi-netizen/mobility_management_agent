const test = require("node:test")
const assert = require("node:assert/strict")

const { formatDate, formatTime } = require("../miniprogram/utils/time")

test("formats ISO timestamps for the user timezone", () => {
  process.env.TZ = "Asia/Shanghai"
  assert.equal(formatTime("2026-08-01T05:15:00+08:00"), "05:15")
  assert.equal(formatDate("2026-08-01T09:20:00+08:00"), "8月1日 周六")
})
