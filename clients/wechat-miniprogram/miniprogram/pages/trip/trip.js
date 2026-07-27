const { request, upload } = require("../../utils/request")
const {
  formatDate,
  formatTime,
  localDateParts,
  toChinaIso,
  todayDate,
} = require("../../utils/time")
const {
  RISK_OPTIONS,
  normalizeTrip,
  riskIndexFor,
  validateTrip,
} = require("../../utils/trip")

const INTAKE_OPTIONS = [
  { label: "短信/通知", value: "text" },
  { label: "ICS 日历", value: "ics" },
  { label: "截图 OCR", value: "image" },
]

Page({
  data: {
    loading: true,
    saving: false,
    parsing: false,
    error: "",
    intakeOptions: INTAKE_OPTIONS,
    intakeMode: "text",
    intakeText: "【携程行程通知示例】CA1832 杭州萧山机场 T4 → 北京首都机场，2026/8/1 09:20 起飞",
    intakeImagePath: "",
    intakeImageName: "",
    candidate: null,
    candidateTime: "",
    candidateRedactions: "",
    draft: {
      flight_number: "",
      departure_airport: "",
      destination_airport: "",
      terminal: "",
      departure_place: "",
      checked_baggage: false,
      accessibility_assistance: false,
      risk_profile: "cautious",
      live_data_consent: false,
      model_egress_consent: false,
      itinerary_source: "manual",
      user_disruption_notes: [],
    },
    departureDate: "",
    departureTime: "",
    longitude: "",
    latitude: "",
    disruptionNotes: "",
    minimumDate: "",
    riskOptions: RISK_OPTIONS,
    riskIndex: 1,
  },

  onLoad() {
    this.setData({ minimumDate: todayDate() })
  },

  onShow() {
    const app = getApp()
    const trip = app.globalData.trip
    const candidate = app.globalData.tripCandidate
    if (candidate) this.showCandidate(candidate)
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
        error: error.message || "无法载入示例行程",
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
      longitude: value.departure_coordinates
        ? String(value.departure_coordinates.longitude)
        : "",
      latitude: value.departure_coordinates
        ? String(value.departure_coordinates.latitude)
        : "",
      disruptionNotes: value.user_disruption_notes.join("\n"),
      riskIndex: riskIndexFor(value.risk_profile),
    })
  },

  handleIntakeMode(event) {
    this.setData({
      intakeMode: event.currentTarget.dataset.mode,
      candidate: null,
      error: "",
    })
  },

  handleIntakeText(event) {
    this.setData({ intakeText: event.detail.value, candidate: null, error: "" })
  },

  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sourceType: ["album", "camera"],
      sizeType: ["compressed"],
      success: (result) => {
        const file = result.tempFiles && result.tempFiles[0]
        if (!file) return
        if (file.size > 5 * 1024 * 1024) {
          wx.showToast({ title: "图片需小于 5 MB", icon: "none" })
          return
        }
        const name = String(file.tempFilePath).split("/").pop() || "行程截图"
        this.setData({
          intakeImagePath: file.tempFilePath,
          intakeImageName: name,
          candidate: null,
          error: "",
        })
      },
    })
  },

  async parseIntake() {
    if (this.data.parsing) return
    const isImage = this.data.intakeMode === "image"
    if (isImage && !this.data.intakeImagePath) {
      wx.showToast({ title: "请先选择行程截图", icon: "none" })
      return
    }
    if (!isImage && !String(this.data.intakeText).trim()) {
      wx.showToast({ title: "请先粘贴行程内容", icon: "none" })
      return
    }
    this.setData({ parsing: true, candidate: null, error: "" })
    try {
      const common = {
        departure_place: this.data.draft.departure_place || "待确认出发地",
        checked_baggage: String(Boolean(this.data.draft.checked_baggage)),
        risk_profile: this.data.draft.risk_profile || "cautious",
      }
      const candidate = isImage
        ? await upload(
          "/api/v1/trips/candidates/image",
          this.data.intakeImagePath,
          common,
        )
        : await request("/api/v1/trips/candidates", {
          method: "POST",
          data: {
            source_type: this.data.intakeMode,
            content: this.data.intakeText,
            departure_place: common.departure_place,
            checked_baggage: this.data.draft.checked_baggage,
            risk_profile: common.risk_profile,
          },
          timeout: 30000,
        })
      getApp().globalData.tripCandidate = candidate
      this.showCandidate(candidate)
    } catch (error) {
      this.setData({ error: error.message || "行程解析失败" })
    } finally {
      this.setData({ parsing: false })
    }
  },

  showCandidate(candidate) {
    const candidateTime = candidate && candidate.scheduled_departure
      ? `${formatDate(candidate.scheduled_departure)} ${formatTime(candidate.scheduled_departure)}`
      : "待确认"
    const candidateRedactions = candidate
      && Array.isArray(candidate.redactions_applied)
      && candidate.redactions_applied.length
      ? candidate.redactions_applied.join("、")
      : "未检测到敏感字段"
    this.setData({ candidate, candidateTime, candidateRedactions })
  },

  applyCandidate() {
    const candidate = this.data.candidate
    if (!candidate) return
    const merged = normalizeTrip({
      ...this.data.draft,
      flight_number: candidate.flight_number || this.data.draft.flight_number,
      departure_airport:
        candidate.departure_airport || this.data.draft.departure_airport,
      destination_airport:
        candidate.destination_airport || this.data.draft.destination_airport,
      terminal: candidate.terminal || this.data.draft.terminal,
      scheduled_departure:
        candidate.scheduled_departure
        || toChinaIso(this.data.departureDate, this.data.departureTime),
      departure_place: candidate.departure_place,
      checked_baggage: candidate.checked_baggage,
      risk_profile: candidate.risk_profile,
      itinerary_source: candidate.itinerary_source || "other",
    })
    getApp().globalData.tripCandidate = null
    this.setData({ candidate: null })
    this.applyTrip(merged)
    wx.showToast({ title: "已带入，请逐项确认", icon: "none" })
  },

  handleTextInput(event) {
    const field = event.currentTarget.dataset.field
    if (!field) return
    this.setData({ [`draft.${field}`]: event.detail.value })
  },

  handleCoordinateInput(event) {
    const field = event.currentTarget.dataset.field
    if (field === "longitude" || field === "latitude") {
      this.setData({ [field]: event.detail.value })
    }
  },

  handleNotesInput(event) {
    this.setData({ disruptionNotes: event.detail.value })
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

  handleBooleanChange(event) {
    const field = event.currentTarget.dataset.field
    if (!field) return
    this.setData({ [`draft.${field}`]: Boolean(event.detail.value) })
  },

  saveTrip() {
    const hasLongitude = String(this.data.longitude).trim() !== ""
    const hasLatitude = String(this.data.latitude).trim() !== ""
    if (hasLongitude !== hasLatitude) {
      this.setData({ error: "经度和纬度必须同时填写或同时留空" })
      return
    }
    const candidate = normalizeTrip({
      ...this.data.draft,
      scheduled_departure: toChinaIso(
        this.data.departureDate,
        this.data.departureTime,
      ),
      departure_coordinates: hasLongitude
        ? {
            longitude: Number(this.data.longitude),
            latitude: Number(this.data.latitude),
          }
        : null,
      user_disruption_notes: String(this.data.disruptionNotes)
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean)
        .slice(0, 5),
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
    app.globalData.tripCandidate = null
    wx.switchTab({
      url: "/pages/index/index",
      complete: () => this.setData({ saving: false }),
    })
  },

  retry() {
    this.loadDemo()
  },
})
