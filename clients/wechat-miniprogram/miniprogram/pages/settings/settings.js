const {
  DEFAULT_ENVIRONMENT,
  ENVIRONMENTS,
  clearRuntimeConfig,
  getRuntimeConfig,
  saveEnvironment,
} = require("../../config")
const { accountAppId, request } = require("../../utils/request")

const environmentOptions = [
  ENVIRONMENTS.production,
  ENVIRONMENTS.local,
]

Page({
  data: {
    environmentOptions,
    environmentIndex: 0,
    config: ENVIRONMENTS.production,
    appId: "未知",
    testing: false,
    testStatus: "idle",
    testMessage: "",
    health: null,
    capabilities: null,
  },

  onLoad() {
    this.refreshConfig()
  },

  onShow() {
    this.refreshConfig()
  },

  refreshConfig() {
    const config = getRuntimeConfig()
    const environmentIndex = Math.max(
      0,
      environmentOptions.findIndex((item) => item.id === config.environment),
    )
    this.setData({
      config,
      environmentIndex,
      appId: accountAppId(),
    })
  },

  handleEnvironmentChange(event) {
    const environmentIndex = Number(event.detail.value)
    const config = saveEnvironment(environmentOptions[environmentIndex].id)
    this.setData({
      config,
      environmentIndex,
      testStatus: "idle",
      testMessage: "",
      health: null,
      capabilities: null,
    })
  },

  async testConnection() {
    this.setData({
      testing: true,
      testStatus: "idle",
      testMessage: "",
      health: null,
      capabilities: null,
    })
    try {
      const [health, capabilities] = await Promise.all([
        request("/health", { timeout: 12000 }),
        request("/api/v1/capabilities", { timeout: 12000 }),
      ])
      if (health.status !== "ok") throw new Error("健康检查没有返回 ok")
      if (health.data_scope !== "synthetic" || capabilities.data_scope !== "synthetic") {
        throw new Error("数据范围与当前小程序安全边界不一致")
      }
      if (capabilities.provider !== "fake") {
        throw new Error("当前版本只允许使用 FakeProvider")
      }
      this.setData({
        testing: false,
        testStatus: "success",
        testMessage: "服务、能力契约和合成数据边界均正常",
        health,
        capabilities,
      })
    } catch (error) {
      this.setData({
        testing: false,
        testStatus: "error",
        testMessage: error.message || "连接测试失败",
      })
    }
  },

  resetEnvironment() {
    const config = clearRuntimeConfig()
    this.setData({
      config,
      environmentIndex: environmentOptions.findIndex(
        (item) => item.id === DEFAULT_ENVIRONMENT,
      ),
      testStatus: "idle",
      testMessage: "已恢复阿里云正式入口",
      health: null,
      capabilities: null,
    })
  },

  openAbout() {
    wx.navigateTo({ url: "/pages/about/about" })
  },
})
