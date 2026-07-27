const { apiBase } = require("../config")

function request(path, options = {}) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${apiBase}${path}`,
      method: options.method || "GET",
      data: options.data,
      header: {
        "content-type": "application/json",
      },
      timeout: 10000,
      success(response) {
        if (response.statusCode >= 200 && response.statusCode < 300) {
          resolve(response.data)
          return
        }
        reject(new Error(`服务返回 ${response.statusCode}`))
      },
      fail(error) {
        reject(new Error(error.errMsg || "网络请求失败"))
      },
    })
  })
}

module.exports = { request }
