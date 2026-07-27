const { request } = require("../../utils/request")
const { localDateParts, toChinaIso, todayDate } = require("../../utils/time")
const {
  RISK_OPTIONS,
  normalizeTrip,
  riskIndexFor,
  validateTrip,
} = require("../../utils/trip")

Page({
  data: {
    loading: true,
    saving: false,
    error: "",
    draft: {
      flight_number: "",
      departure_airport: "",
      terminal: "",
      departure_place: "",
      checked_baggage: false,
      risk_profile: "cautious",
    },
    departureDate: "",
    departureTime: "",
    minimumDate: "",
    riskOptions: RISK_OPTIONS,
    riskIndex: 1,
  },

  onLoad() {
    this.setData({ minimumDate: todayDate() })
  },

  onShow() {
    const trip = getApp().globalData.trip
    if (trip) {
      this.applyTrip(trip)
      return
    }
    this.loadDemo()
  },

  async loadDemo() {
    this.setData({ loading: true, error: "" })
    try {
      const trip = await request("/api/v1/demo/trip")
      this.applyTrip(trip)
    } catch (error) {
      this.setData({
        loading: false,
        error: error.message || "无法载入合成行程",
      })
    }
  },

  applyTrip(trip) {
    const value = normalizeTrip(trip)
    const parts = localDateParts(value.scheduled_departure)
    this.setData({
      loading: false,
      error: "",
      draft: value,
      departureDate: parts.date,
      departureTime: parts.time,
      riskIndex: riskIndexFor(value.risk_profile),
    })
  },

  handleTextInput(event) {
    const field = event.currentTarget.dataset.field
    if (!field) return
    this.setData({ [`draft.${field}`]: event.detail.value })
  },

  handleDateChange(event) {
    this.setData({ departureDate: event.detail.value })
  },

  handleTimeChange(event) {
    this.setData({ departureTime: event.detail.value })
  },

  handleRiskChange(event) {
    const riskIndex = Number(event.detail.value)
    this.setData({
      riskIndex,
      "draft.risk_profile": RISK_OPTIONS[riskIndex].value,
    })
  },

  handleBaggageChange(event) {
    this.setData({ "draft.checked_baggage": Boolean(event.detail.value) })
  },

  saveTrip() {
    const candidate = normalizeTrip({
      ...this.data.draft,
      scheduled_departure: toChinaIso(this.data.departureDate, this.data.departureTime),
    })
    const validation = validateTrip(candidate)
    if (!validation.valid) {
      this.setData({ error: validation.message })
      wx.showToast({ title: validation.message, icon: "none", duration: 2600 })
      return
    }

    this.setData({ saving: true, error: "" })
    const app = getApp()
    app.globalData.trip = validation.trip
    app.globalData.tripRevision += 1
    app.globalData.decision = null
    app.globalData.decisionRevision = -1
    wx.switchTab({
      url: "/pages/index/index",
      complete: () => this.setData({ saving: false }),
    })
  },

  retry() {
    this.loadDemo()
  },
})
