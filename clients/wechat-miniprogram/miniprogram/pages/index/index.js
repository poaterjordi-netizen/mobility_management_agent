const { request } = require("../../utils/request")
const { buildDecisionView } = require("../../utils/decision-view")
const { formatDate, formatTime } = require("../../utils/time")
const { RISK_OPTIONS, riskIndexFor } = require("../../utils/trip")

Page({
  data: {
    loading: true,
    calculating: false,
    workflowBusy: "",
    error: "",
    trip: null,
    result: null,
    capabilities: null,
    serviceVersion: "",
    dataScope: "synthetic",
    riskOptions: RISK_OPTIONS,
    riskIndex: 1,
    leaveTime: "--:--",
    latestTime: "--:--",
    terminalTime: "--:--",
    departureTime: "--:--",
    checkinCloseTime: "--:--",
    departureDate: "",
    verifiedLabel: "",
    confidenceLabel: "",
    evidenceCount: 0,
    reminder: null,
    reminderTime: "",
    actionProposal: null,
    actionParameters: [],
    question: "为什么建议这个时间出发？",
    answer: null,
    citedEvidence: "",
    telemetryLabel: "",
    telemetryTime: "",
    metarLabel: "",
    metarTime: "",
    sourceWarnings: [],
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
      app.globalData.dataScope = capabilities.data_scope
      this.setData({
        capabilities,
        serviceVersion: health.version || capabilities.version || "",
        dataScope: capabilities.data_scope || health.data_scope || "synthetic",
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
        error: error.message || "暂时无法连接服务",
      })
    }
  },

  async calculate(trip = this.data.trip) {
    if (!trip) return
    const sequence = ++this._requestSequence
    this.setData({
      calculating: true,
      error: "",
      trip,
      riskIndex: riskIndexFor(trip.risk_profile),
      reminder: null,
      actionProposal: null,
      answer: null,
    })
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
      dataScope: result.context.data_scope,
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

  async previewReminder() {
    if (!this.data.result || this.data.workflowBusy) return
    this.setData({ workflowBusy: "reminder", error: "" })
    try {
      const reminder = await request("/api/v1/reminders/preview", {
        method: "POST",
        data: {
          trip: this.data.result.trip,
          decision: this.data.result.decision,
          lead_hours: 24,
        },
      })
      this.setData({
        reminder,
        reminderTime: `${formatDate(reminder.remind_at)} ${formatTime(reminder.remind_at)}`,
      })
    } catch (error) {
      this.setData({ error: error.message || "提醒生成失败" })
    } finally {
      this.setData({ workflowBusy: "" })
    }
  },

  copyReminder() {
    const reminder = this.data.reminder
    if (!reminder) return
    wx.setClipboardData({
      data: `${reminder.title}\n${this.data.reminderTime}\n${reminder.message}`,
      success() {
        wx.showToast({ title: "提醒内容已复制", icon: "success" })
      },
    })
  },

  async proposeAction() {
    if (!this.data.result || this.data.workflowBusy) return
    this.setData({ workflowBusy: "action", error: "" })
    try {
      const actionProposal = await request("/api/v1/action-proposals", {
        method: "POST",
        data: {
          trip: this.data.result.trip,
          decision: this.data.result.decision,
          action_type: "open_ride_hailing",
        },
      })
      const actionParameters = Object.entries(
        actionProposal.parameters_preview || {},
      ).map(([label, value]) => ({ label, value }))
      this.setData({ actionProposal, actionParameters })
    } catch (error) {
      this.setData({ error: error.message || "地图提案生成失败" })
    } finally {
      this.setData({ workflowBusy: "" })
    }
  },

  confirmAction() {
    const proposal = this.data.actionProposal
    if (!proposal) return
    wx.showModal({
      title: "确认打开官方地图",
      content: "将复制高德官方链接；不会自动下单或付款。是否继续？",
      confirmText: "确认复制",
      success(result) {
        if (!result.confirm) return
        wx.setClipboardData({
          data: proposal.deep_link,
          success() {
            wx.showToast({ title: "官方链接已复制", icon: "success" })
          },
        })
      },
    })
  },

  copyEvidenceSource(event) {
    const url = event.currentTarget.dataset.url
    if (!url) return
    wx.setClipboardData({
      data: url,
      success() {
        wx.showToast({ title: "来源链接已复制", icon: "success" })
      },
    })
  },

  handleQuestion(event) {
    this.setData({ question: event.detail.value })
  },

  async askQuestion() {
    if (!this.data.result || !String(this.data.question).trim()) return
    this.setData({ workflowBusy: "question", error: "" })
    try {
      const answer = await request("/api/v1/assistant/questions", {
        method: "POST",
        data: {
          question: String(this.data.question).trim(),
          decision: this.data.result,
        },
      })
      this.setData({
        answer,
        citedEvidence: (answer.cited_evidence_ids || []).join("、"),
      })
    } catch (error) {
      this.setData({ error: error.message || "问答失败" })
    } finally {
      this.setData({ workflowBusy: "" })
    }
  },

  clearSession() {
    wx.showModal({
      title: "清空本次会话",
      content: "将清除当前小程序内存中的行程、建议和候选内容。",
      confirmText: "确认清空",
      success: async (result) => {
        if (!result.confirm) return
        try {
          await request("/api/v1/privacy/session", { method: "DELETE" })
        } catch (_) {
          // 服务端当前不持久化，本地清空仍可安全完成。
        }
        const app = getApp()
        app.globalData.trip = null
        app.globalData.tripRevision += 1
        app.globalData.decision = null
        app.globalData.decisionRevision = -1
        app.globalData.tripCandidate = null
        this.setData({
          result: null,
          trip: null,
          reminder: null,
          actionProposal: null,
          answer: null,
        })
        this.bootstrap({ forceDemo: true })
      },
    })
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
