const test = require("node:test")
const assert = require("node:assert/strict")

global.wx = {
  getAccountInfoSync() {
    return { miniProgram: { appId: "wx-test-app" } }
  },
}

const {
  networkFailureMessage,
  responseMessage,
} = require("../miniprogram/utils/request")

test("explains WeChat request-domain failures with the active AppID and domain", () => {
  const message = networkFailureMessage(
    "https://metro.9m-zx.com/mobility/health",
    { errMsg: "request:fail url not in domain list" },
  )
  assert.match(message, /wx-test-app/)
  assert.match(message, /https:\/\/metro\.9m-zx\.com/)
  assert.match(message, /服务器域名/)
})

test("preserves ordinary network errors and formats validation responses", () => {
  assert.equal(
    networkFailureMessage("https://example.test", { errMsg: "request:fail timeout" }),
    "request:fail timeout",
  )
  assert.equal(
    responseMessage({
      statusCode: 422,
      data: { detail: [{ msg: "航班号格式错误" }, { msg: "日期无效" }] },
    }),
    "航班号格式错误；日期无效",
  )
})
