const { getRuntimeConfig } = require("../config")

function responseMessage(response) {
  const body = response && response.data
  if (body && typeof body.detail === "string") return body.detail
  if (body && Array.isArray(body.detail) && body.detail.length) {
    return body.detail.map((item) => item.msg || "参数错误").join("；")
  }
  return `服务返回异常（${(response && response.statusCode) || "未知"}）`
}

function accountAppId() {
  try {
    const account = wx.getAccountInfoSync && wx.getAccountInfoSync()
    return (account && account.miniProgram && account.miniProgram.appId) || "未知"
  } catch (_) {
    return "未知"
  }
}

function networkFailureMessage(url, error) {
  const original = String((error && error.errMsg) || "网络连接失败，请稍后重试")
  if (!/url not in domain list/i.test(original)) return original

  const match = String(url || "").match(/^https?:\/\/[^/]+/i)
  const requestDomain = match ? match[0] : String(url || "未知")
  return `微信 request 合法域名未对当前小程序生效（AppID：${accountAppId()}；请求域名：${requestDomain}）。请在微信公众平台“开发管理 → 开发设置 → 服务器域名”中保存该 request 域名，然后彻底关闭并重新进入小程序。`
}

function request(path, options = {}) {
  const config = getRuntimeConfig()
  const url = `${config.apiBaseUrl}${path}`
  return new Promise((resolve, reject) => {
    wx.request({
      url,
      method: options.method || "GET",
      data: options.data,
      header: {
        "content-type": "application/json",
      },
      timeout: Number(options.timeout || 15000),
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data)
          return
        }
        reject(new Error(responseMessage(response)))
      },
      fail(error) {
        reject(new Error(networkFailureMessage(url, error)))
      },
    })
  })
}

module.exports = {
  accountAppId,
  networkFailureMessage,
  request,
  responseMessage,
}
