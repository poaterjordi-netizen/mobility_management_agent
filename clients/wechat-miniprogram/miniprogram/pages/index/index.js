const { request } = require("../../utils/request")
const { formatDate, formatTime } = require("../../utils/time")

const riskOptions = [
  { label: "标准", value: "standard" },
  { label: "稳妥", value: "cautious" },
  { label: "非常稳妥", value: "very_cautious" },
]

Page({
  data: {
    loading: true,
    error: "",
    trip: null,
    result: null,
    riskOptions,
    riskIndex: 1,
    leaveTime: "--:--",
    latestTime: "--:--",
    terminalTime: "--:--",
    departureTime: "--:--",
    departureDate: "",
  },

  onLoad() {
    this.loadDemo()
  },

  onPullDownRefresh() {
    this.loadDemo().finally(() => wx.stopPullDownRefresh())
  },

  async loadDemo() {
    this.setData({ loading: true, error: "" })
    try {
      const trip = await request("/api/v1/demo/trip")
      const riskIndex = Math.max(
        0,
        riskOptions.findIndex((item) => item.value === trip.risk_profile),
      )
      this.setData({ trip, riskIndex })
      await this.calculate()
    } catch (error) {
      this.setData({
        loading: false,
        error: error.message || "暂时无法连接演示服务",
      })
    }
  },

  async calculate() {
    if (!this.data.trip) return
    this.setData({ loading: true, error: "" })
    try {
      const result = await request("/api/v1/decisions/preview", {
        method: "POST",
        data: this.data.trip,
      })
      this.setData({
        result,
        loading: false,
        leaveTime: formatTime(result.decision.recommended_leave_at),
        latestTime: formatTime(result.decision.latest_reasonable_leave_at),
        terminalTime: formatTime(result.decision.target_terminal_arrival),
        departureTime: formatTime(result.decision.scheduled_departure),
        departureDate: formatDate(result.decision.scheduled_departure),
      })
    } catch (error) {
      this.setData({
        loading: false,
        error: error.message || "生成建议失败",
      })
    }
  },

  handleRiskChange(event) {
    const riskIndex = Number(event.detail.value)
    this.setData({
      riskIndex,
      "trip.risk_profile": riskOptions[riskIndex].value,
    })
    this.calculate()
  },

  handleBaggageChange(event) {
    this.setData({
      "trip.checked_baggage": event.detail.value,
    })
    this.calculate()
  },

  retry() {
    this.loadDemo()
  },
})
