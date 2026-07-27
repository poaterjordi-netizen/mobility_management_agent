const { request } = require("../../utils/request")
const { buildDecisionView } = require("../../utils/decision-view")
const { RISK_OPTIONS, riskIndexFor } = require("../../utils/trip")

Page({
  data: {
    loading: true,
    calculating: false,
    error: "",
    trip: null,
    result: null,
    capabilities: null,
    serviceVersion: "",
    riskOptions: RISK_OPTIONS,
    riskIndex: 1,
    leaveTime: "--:--",
    latestTime: "--:--",
    terminalTime: "--:--",
    departureTime: "--:--",
    departureDate: "",
    verifiedLabel: "",
    confidenceLabel: "",
    evidenceCount: 0,
  },

  onLoad() {
    this._loaded = true
    this._requestSequence = 0
    this.bootstrap()
  },

  onShow() {
    if (!this._loaded) return
    const app = getApp()
    const trip = app.globalData.trip
    if (!trip) return
    if (
      app.globalData.decision
      && app.globalData.decisionRevision === app.globalData.tripRevision
    ) {
      this.applyResult(app.globalData.decision)
      return
    }
    this.calculate(trip)
  },

  onPullDownRefresh() {
    this.bootstrap({ forceDemo: false }).finally(() => wx.stopPullDownRefresh())
  },

  async bootstrap(options = {}) {
    this.setData({ loading: true, error: "" })
    try {
      const app = getApp()
      const [health, capabilities] = await Promise.all([
        request("/health"),
        request("/api/v1/capabilities"),
      ])
      let trip = app.globalData.trip
      if (!trip || options.forceDemo) {
        trip = await request("/api/v1/demo/trip")
        app.globalData.trip = trip
        app.globalData.tripRevision += 1
      }
      app.globalData.capabilities = capabilities
      this.setData({
        capabilities,
        serviceVersion: health.version || capabilities.version || "",
      })
      if (
        app.globalData.decision
        && app.globalData.decisionRevision === app.globalData.tripRevision
      ) {
        this.applyResult(app.globalData.decision)
      } else {
        await this.calculate(trip)
      }
    } catch (error) {
      this.setData({
        loading: false,
        calculating: false,
        error: error.message || "暂时无法连接演示服务",
      })
    }
  },

  async calculate(trip = this.data.trip) {
    if (!trip) return
    const sequence = ++this._requestSequence
    this.setData({ calculating: true, error: "", trip, riskIndex: riskIndexFor(trip.risk_profile) })
    try {
      const result = await request("/api/v1/decisions/preview", {
        method: "POST",
        data: trip,
      })
      if (sequence !== this._requestSequence) return
      const app = getApp()
      app.globalData.trip = result.trip
      app.globalData.decision = result
      app.globalData.decisionRevision = app.globalData.tripRevision
      this.applyResult(result)
    } catch (error) {
      if (sequence !== this._requestSequence) return
      this.setData({
        loading: false,
        calculating: false,
        error: error.message || "生成建议失败",
      })
    }
  },

  applyResult(result) {
    const view = buildDecisionView(result)
    if (!view) return
    this.setData({
      result,
      trip: result.trip,
      riskIndex: riskIndexFor(result.trip.risk_profile),
      loading: false,
      calculating: false,
      error: "",
      ...view,
    })
  },

  handleRiskChange(event) {
    const riskIndex = Number(event.detail.value)
    const trip = {
      ...this.data.trip,
      risk_profile: RISK_OPTIONS[riskIndex].value,
    }
    const app = getApp()
    app.globalData.trip = trip
    app.globalData.tripRevision += 1
    this.setData({ riskIndex, trip })
    this.calculate(trip)
  },

  handleBaggageChange(event) {
    const trip = {
      ...this.data.trip,
      checked_baggage: event.detail.value,
    }
    const app = getApp()
    app.globalData.trip = trip
    app.globalData.tripRevision += 1
    this.setData({ trip })
    this.calculate(trip)
  },

  retry() {
    this.bootstrap({ forceDemo: false })
  },

  goTrip() {
    wx.switchTab({ url: "/pages/trip/trip" })
  },

  goSettings() {
    wx.switchTab({ url: "/pages/settings/settings" })
  },
})
