import {
  ArrowRight,
  BadgeCheck,
  BellRing,
  CalendarDays,
  ChevronRight,
  CircleAlert,
  Clock3,
  CloudRain,
  Database,
  FileText,
  ImageUp,
  LockKeyhole,
  MapPin,
  MapPinned,
  MessageCircleQuestion,
  Navigation,
  Plane,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  TimerReset,
  Upload,
} from "lucide-react"
import {
  type ChangeEvent,
  type FormEvent,
  useCallback,
  useEffect,
  useId,
  useMemo,
  useState,
} from "react"
import {
  askAssistant,
  deleteServerSession,
  getCapabilities,
  getDemoTrip,
  getPrivacyExport,
  getSources,
  parseTripCandidate,
  parseTripImage,
  previewDecision,
  previewReminder,
  proposeAction,
} from "./api"
import type { components } from "./api-schema"

type TripInput = components["schemas"]["TripInput"]
type TripCandidate = components["schemas"]["TripCandidate"]
type DecisionResponse = components["schemas"]["DecisionResponse"]
type Capabilities = components["schemas"]["CapabilitiesResponse"]
type SourceStatus = components["schemas"]["SourceStatus"]
type ReminderPreview = components["schemas"]["ReminderPreview"]
type ActionProposal = components["schemas"]["ActionProposal"]
type AssistantAnswer = components["schemas"]["AssistantAnswer"]
type IntakeMode = "text" | "ics" | "image"

const riskLabels: Record<TripInput["risk_profile"], string> = {
  standard: "标准",
  cautious: "稳妥",
  very_cautious: "非常稳妥",
}

const sourceModeLabels: Record<SourceStatus["mode"], string> = {
  available: "可用",
  configured: "已配置",
  synthetic: "规则降级",
  blocked: "受门禁保护",
  unavailable: "不可用",
}

const congestionLabels = {
  low: "畅通",
  medium: "缓行",
  high: "拥堵",
  unknown: "路况未知",
} as const

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value))
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(new Date(value))
}

function formatDateTime(value: string) {
  return `${formatDate(value)} ${formatTime(value)}`
}

function toLocalInput(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ""
  const chinaTime = new Date(date.getTime() + 8 * 60 * 60 * 1000)
  return chinaTime.toISOString().slice(0, 16)
}

function fromLocalInput(value: string) {
  return `${value}:00+08:00`
}

function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = name
  anchor.click()
  URL.revokeObjectURL(url)
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="section-label">{children}</div>
}

function LoadingCard() {
  return (
    <output className="loading-card" aria-label="正在生成出发建议">
      <div className="loading-line wide" />
      <div className="loading-line medium" />
      <div className="loading-grid">
        <div />
        <div />
        <div />
      </div>
    </output>
  )
}

const bjtuDutExample: TripInput = {
  flight_number: "CA8908",
  departure_airport: "PEK",
  destination_airport: "DLC",
  terminal: "T3",
  scheduled_departure: "2026-07-27T21:50:00+08:00",
  departure_place: "北京交通大学（海淀校区）",
  departure_coordinates: {
    longitude: 116.342757,
    latitude: 39.952311,
  },
  checked_baggage: true,
  accessibility_assistance: false,
  risk_profile: "cautious",
  live_data_consent: true,
  model_egress_consent: false,
  itinerary_source: "ctrip",
  user_disruption_notes: [],
}

const bjtuDutIntake =
  "【携程公开时刻测试】CA8908 北京首都国际机场 T3 → 大连周水子国际机场，2026/7/27 21:50 起飞。出发地：北京交通大学海淀校区。"

export function App() {
  const decisionSectionId = useId()
  const intakeSectionId = useId()
  const actionSectionId = useId()
  const sourcesSectionId = useId()
  const editTripTitleId = useId()
  const [trip, setTrip] = useState<TripInput | null>(null)
  const [decision, setDecision] = useState<DecisionResponse | null>(null)
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [sources, setSources] = useState<SourceStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [editing, setEditing] = useState(false)

  const [intakeMode, setIntakeMode] = useState<IntakeMode>("text")
  const [intakeText, setIntakeText] = useState("")
  const [departurePlace, setDeparturePlace] = useState("")
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [candidate, setCandidate] = useState<TripCandidate | null>(null)
  const [intakeBusy, setIntakeBusy] = useState(false)
  const [intakeError, setIntakeError] = useState("")
  const [showBjtuDutJourney, setShowBjtuDutJourney] = useState(false)

  const [reminder, setReminder] = useState<ReminderPreview | null>(null)
  const [actionProposal, setActionProposal] = useState<ActionProposal | null>(null)
  const [workflowBusy, setWorkflowBusy] = useState("")
  const [question, setQuestion] = useState("为什么建议这个时间出发？")
  const [answer, setAnswer] = useState<AssistantAnswer | null>(null)
  const [privacyMessage, setPrivacyMessage] = useState("")

  const calculate = useCallback(async (nextTrip: TripInput) => {
    setLoading(true)
    setError("")
    setReminder(null)
    setActionProposal(null)
    setAnswer(null)
    try {
      setDecision(await previewDecision(nextTrip))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "生成建议失败")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    let active = true
    Promise.all([getDemoTrip(), getCapabilities(), getSources()])
      .then(([demoTrip, serviceCapabilities, sourceStatuses]) => {
        if (!active) return
        setTrip(demoTrip)
        setCapabilities(serviceCapabilities)
        setSources(sourceStatuses)
        setLoading(false)
      })
      .catch((requestError) => {
        if (!active) return
        setError(requestError instanceof Error ? requestError.message : "服务连接失败")
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const decisionComponents = decision?.decision.components ?? []
  const totalPreparation = useMemo(
    () => decisionComponents.reduce((sum, component) => sum + component.minutes, 0),
    [decisionComponents],
  )

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!trip) return
    setEditing(false)
    void calculate(trip)
  }

  async function handleParse() {
    if (!trip) return
    if (!departurePlace.trim()) {
      setIntakeError("请先填写“从哪里出发去机场”。")
      return
    }
    setIntakeBusy(true)
    setIntakeError("")
    setCandidate(null)
    setDecision(null)
    setShowBjtuDutJourney(false)
    try {
      const parsed =
        intakeMode === "image"
          ? imageFile
            ? await parseTripImage(imageFile, {
                departure_place: departurePlace.trim(),
                checked_baggage: trip.checked_baggage,
                risk_profile: trip.risk_profile,
              })
            : null
          : await parseTripCandidate({
              source_type: intakeMode,
              content: intakeText,
              departure_place: departurePlace.trim(),
              checked_baggage: trip.checked_baggage,
              risk_profile: trip.risk_profile,
            })
      if (!parsed) throw new Error("请先选择 PNG 或 JPEG 行程截图")
      setCandidate(parsed)
    } catch (requestError) {
      setIntakeError(requestError instanceof Error ? requestError.message : "行程解析失败")
    } finally {
      setIntakeBusy(false)
    }
  }

  function applyCandidate() {
    if (!candidate || !trip) return
    setTrip({
      ...trip,
      flight_number: candidate.flight_number ?? "",
      departure_airport: candidate.departure_airport ?? "",
      destination_airport: candidate.destination_airport,
      terminal: candidate.terminal ?? "",
      scheduled_departure: candidate.scheduled_departure ?? "",
      departure_place: candidate.departure_place,
      departure_coordinates: null,
      checked_baggage: candidate.checked_baggage,
      risk_profile: candidate.risk_profile,
      itinerary_source: candidate.itinerary_source,
      user_disruption_notes: [],
    })
    setCandidate(null)
    setEditing(true)
  }

  async function loadBjtuDutExample() {
    setDeparturePlace(bjtuDutExample.departure_place)
    setIntakeMode("text")
    setIntakeText(bjtuDutIntake)
    setCandidate(null)
    setIntakeError("")
    setTrip(bjtuDutExample)
    setShowBjtuDutJourney(true)
    await calculate(bjtuDutExample)
  }

  async function buildReminder() {
    if (!decision) return
    setWorkflowBusy("reminder")
    setError("")
    try {
      setReminder(await previewReminder(decision))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "提醒生成失败")
    } finally {
      setWorkflowBusy("")
    }
  }

  async function buildAction() {
    if (!decision) return
    setWorkflowBusy("action")
    setError("")
    try {
      setActionProposal(await proposeAction(decision, "open_ride_hailing"))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "地图提案生成失败")
    } finally {
      setWorkflowBusy("")
    }
  }

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!decision || !question.trim()) return
    setWorkflowBusy("question")
    try {
      setAnswer(await askAssistant(question.trim(), decision))
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "问答失败")
    } finally {
      setWorkflowBusy("")
    }
  }

  async function exportPrivacy() {
    setWorkflowBusy("privacy")
    try {
      const payload = await getPrivacyExport()
      download(
        "mobility-privacy-export.json",
        JSON.stringify(payload, null, 2),
        "application/json;charset=utf-8",
      )
      setPrivacyMessage("隐私导出已生成：当前服务端没有持久化个人数据。")
    } finally {
      setWorkflowBusy("")
    }
  }

  async function clearSession() {
    setWorkflowBusy("privacy")
    try {
      const result = await deleteServerSession()
      setDecision(null)
      setTrip(null)
      setCandidate(null)
      setDeparturePlace("")
      setIntakeText("")
      setShowBjtuDutJourney(false)
      setReminder(null)
      setActionProposal(null)
      setAnswer(null)
      setPrivacyMessage(result.note)
    } finally {
      setWorkflowBusy("")
    }
  }

  function handleImage(event: ChangeEvent<HTMLInputElement>) {
    const nextFile = event.target.files?.[0] ?? null
    setImageFile(nextFile)
    setCandidate(null)
    setIntakeError("")
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="topbar">
        <a className="brand" href="/" aria-label="回到首页">
          <span className="brand-mark">
            <Navigation size={18} strokeWidth={2.2} />
          </span>
          <span>
            <strong>行前</strong>
            <small>AI MOBILITY CONCIERGE</small>
          </span>
        </a>
        <nav className="topnav" aria-label="主要功能">
          <a href={`#${intakeSectionId}`}>导入行程</a>
          <a href={`#${decisionSectionId}`}>出发建议</a>
          <a href={`#${actionSectionId}`}>提醒与叫车</a>
          <a href={`#${sourcesSectionId}`}>数据源</a>
        </nav>
        <div className="status-pill">
          <span className="status-dot" />
          {capabilities?.data_scope ?? "synthetic"} · v{capabilities?.version ?? "0.4.1"}
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <Sparkles size={14} />
              从分散行程到一个可核验的出发决定
            </div>
            <h1>
              明天去机场，
              <br />
              <span>应该几点出发？</span>
            </h1>
            <p>
              导入短信、日历或截图，融合航班时间窗、机场流程、道路分位数、天气和事件信号，
              再由确定性引擎计算并完整复核。
            </p>
            <div className="hero-actions">
              <a className="primary-action" href={`#${intakeSectionId}`}>
                开始填写（3 步）
                <ArrowRight size={17} />
              </a>
              <a className="text-action" href={`#${decisionSectionId}`}>
                建议显示在哪里
                <ChevronRight size={16} />
              </a>
            </div>
            <div className="trust-row">
              <span>
                <ShieldCheck size={15} /> 不抓取第三方私有页面
              </span>
              <span>
                <BadgeCheck size={15} /> 所有分钟可重算
              </span>
              <span>
                <LockKeyhole size={15} /> 默认不持久化行程
              </span>
            </div>
          </div>

          <div className="flight-orbit" aria-hidden="true">
            <div className="orbit-ring ring-one" />
            <div className="orbit-ring ring-two" />
            <div className="orbit-card">
              <span>{decision ? "已确认旅程" : "等待填写"}</span>
              <strong>{decision?.trip.flight_number ?? "待导入"}</strong>
              <div>
                <b>{decision?.trip.departure_airport ?? "—"}</b>
                <ArrowRight size={18} />
                <b>{decision?.trip.destination_airport ?? "—"}</b>
              </div>
              <small>
                {decision ? formatDate(decision.trip.scheduled_departure) : "尚未生成建议"}
              </small>
            </div>
            <Plane className="orbit-plane" size={34} />
          </div>
        </section>

        <section className="intake-section" id={intakeSectionId}>
          <div className="section-heading">
            <div>
              <SectionLabel>TRIP UNDERSTANDING</SectionLabel>
              <h2>用 3 步生成出发建议</h2>
            </div>
            <p>先填写去机场的出发地，再粘贴已经订好的航班通知，最后确认系统识别出的字段。</p>
          </div>
          <div className="quick-example">
            <div>
              <strong>想直接看北京交大 → 首都机场 → 大连 → 大连理工测试？</strong>
              <span>
                一键载入已验证的 CA8908 测试数据；它代表“21:50 起飞”，不是“21:00 才离开学校”。
              </span>
            </div>
            <button type="button" onClick={() => void loadBjtuDutExample()}>
              直接查看这条测试建议
              <ArrowRight size={16} />
            </button>
          </div>
          <div className="intake-layout">
            <article className="intake-card">
              <label className="simple-input">
                <b>
                  <span>1</span>
                  从哪里出发去机场？
                </b>
                <input
                  value={departurePlace}
                  onChange={(event) => {
                    setDeparturePlace(event.target.value)
                    setCandidate(null)
                    setIntakeError("")
                  }}
                  placeholder="例如：北京交通大学（海淀校区）"
                />
                <small>这是去机场的起点，不是航班出发机场。</small>
              </label>

              <div className="simple-step-title">
                <span>2</span>
                <div>
                  <b>粘贴已经订好的航班通知</b>
                  <small>必须包含航班号和计划起飞时间；“21:00”不要填写成希望离校的时间。</small>
                </div>
              </div>
              <div className="mode-tabs" role="tablist" aria-label="导入方式">
                <button
                  className={intakeMode === "text" ? "active" : ""}
                  type="button"
                  onClick={() => setIntakeMode("text")}
                >
                  <FileText size={16} /> 短信/通知
                </button>
                <button
                  className={intakeMode === "ics" ? "active" : ""}
                  type="button"
                  onClick={() => setIntakeMode("ics")}
                >
                  <CalendarDays size={16} /> ICS 日历
                </button>
                <button
                  className={intakeMode === "image" ? "active" : ""}
                  type="button"
                  onClick={() => setIntakeMode("image")}
                >
                  <ImageUp size={16} /> 截图 OCR
                </button>
              </div>

              {intakeMode === "image" ? (
                <label className="upload-drop">
                  <Upload size={26} />
                  <strong>{imageFile?.name ?? "选择 PNG 或 JPEG 行程截图"}</strong>
                  <span>最大 5 MB；服务端本地 OCR，临时文件在响应后删除</span>
                  <input type="file" accept="image/png,image/jpeg" onChange={handleImage} />
                </label>
              ) : (
                <label className="intake-field">
                  <span>{intakeMode === "ics" ? "粘贴 ICS 内容" : "粘贴短信、通知或邮件正文"}</span>
                  <textarea
                    value={intakeText}
                    onChange={(event) => {
                      setIntakeText(event.target.value)
                      setCandidate(null)
                      setIntakeError("")
                    }}
                    rows={7}
                    placeholder={
                      intakeMode === "ics"
                        ? "BEGIN:VCALENDAR…"
                        : "例如：【国航】CA8908，北京首都 T3 → 大连周水子，2026/7/27 21:50 起飞"
                    }
                  />
                </label>
              )}
              <button
                className="primary-action parse-action"
                type="button"
                disabled={intakeBusy || (intakeMode === "image" ? !imageFile : !intakeText.trim())}
                onClick={() => void handleParse()}
              >
                {intakeBusy ? <RefreshCw className="spin" size={17} /> : <Sparkles size={17} />}
                解析航班通知
              </button>
              {intakeError && <div className="inline-error">{intakeError}</div>}
            </article>

            <article className="candidate-card">
              <SectionLabel>STEP 3 · CONFIRM</SectionLabel>
              {candidate ? (
                <>
                  <div className="candidate-head">
                    <h3>{candidate.flight_number ?? "航班号待确认"}</h3>
                    <span>
                      {candidate.itinerary_source} · {candidate.source_type}
                    </span>
                  </div>
                  <dl className="candidate-fields">
                    <div>
                      <dt>机场</dt>
                      <dd>
                        {candidate.departure_airport ?? "待确认"} →{" "}
                        {candidate.destination_airport ?? "待确认"}
                      </dd>
                    </div>
                    <div>
                      <dt>航站楼</dt>
                      <dd>{candidate.terminal ?? "待确认"}</dd>
                    </div>
                    <div>
                      <dt>计划起飞</dt>
                      <dd>
                        {candidate.scheduled_departure
                          ? formatDateTime(candidate.scheduled_departure)
                          : "待确认"}
                      </dd>
                    </div>
                    <div>
                      <dt>已遮盖</dt>
                      <dd>{candidate.redactions_applied.join("、") || "未检测到敏感字段"}</dd>
                    </div>
                  </dl>
                  {candidate.warnings.map((warning) => (
                    <p className="candidate-warning" key={warning}>
                      <CircleAlert size={14} /> {warning}
                    </p>
                  ))}
                  <button className="confirm-candidate" type="button" onClick={applyCandidate}>
                    确认识别结果并生成建议 <ArrowRight size={16} />
                  </button>
                </>
              ) : (
                <div className="candidate-empty">
                  <ShieldCheck size={30} />
                  <strong>这里会显示航班识别结果</strong>
                  <span>检查航班号、机场、航站楼和起飞时间后，才会生成你的建议。</span>
                </div>
              )}
            </article>
          </div>
        </section>

        <section className="decision-section" id={decisionSectionId}>
          <div className="section-heading">
            <div>
              <SectionLabel>YOUR NEXT DEPARTURE</SectionLabel>
              <h2>下一次出发建议</h2>
            </div>
            <button
              className="refresh-button"
              type="button"
              disabled={!trip || loading}
              onClick={() => trip && void calculate(trip)}
            >
              <RefreshCw size={15} className={loading ? "spin" : ""} />
              刷新全部来源
            </button>
          </div>

          {error ? (
            <div className="error-card" role="alert">
              <CircleAlert size={20} />
              <div>
                <strong>暂时无法完成操作</strong>
                <span>{error}</span>
              </div>
            </div>
          ) : loading ? (
            <LoadingCard />
          ) : !decision ? (
            <div className="decision-empty">
              <MapPinned size={28} />
              <div>
                <strong>生成后，最重要的建议就在这里</strong>
                <span>
                  页面会首先显示“建议几点离开出发地”和“最晚参考时间”。现在还没有使用任何演示行程代替你的输入。
                </span>
              </div>
              <a href={`#${intakeSectionId}`}>返回上方填写行程</a>
            </div>
          ) : (
            <>
              <div className="decision-grid">
                <article className="recommendation-card">
                  <div className="recommendation-topline">
                    <span className="verified-badge">
                      <BadgeCheck size={16} />
                      确定性核验通过
                    </span>
                    <span className="risk-badge">
                      {riskLabels[decision.trip.risk_profile]}方案 · {decision.decision.confidence}{" "}
                      置信度
                    </span>
                  </div>

                  <div className="leave-time">
                    <span>建议离开出发地</span>
                    <strong>{formatTime(decision.decision.recommended_leave_at)}</strong>
                    <small>
                      最晚参考时间 {formatTime(decision.decision.latest_reasonable_leave_at)}
                    </small>
                  </div>

                  <div className="timeline">
                    <div className="timeline-line" />
                    <div className="timeline-point active">
                      <span className="point-icon">
                        <MapPin size={16} />
                      </span>
                      <div>
                        <strong>{formatTime(decision.decision.recommended_leave_at)}</strong>
                        <small>离开出发地</small>
                      </div>
                    </div>
                    <div className="timeline-point">
                      <span className="point-icon">
                        <Route size={16} />
                      </span>
                      <div>
                        <strong>{formatTime(decision.decision.target_terminal_arrival)}</strong>
                        <small>
                          到达 {decision.trip.departure_airport} {decision.trip.terminal}
                        </small>
                      </div>
                    </div>
                    <div className="timeline-point">
                      <span className="point-icon">
                        <Plane size={16} />
                      </span>
                      <div>
                        <strong>{formatTime(decision.decision.scheduled_departure)}</strong>
                        <small>计划起飞</small>
                      </div>
                    </div>
                  </div>

                  <div className="assistant-note">
                    <Sparkles size={18} />
                    <p>{decision.assistant_summary}</p>
                  </div>
                </article>

                <aside className="trip-card">
                  <div className="trip-card-head">
                    <div>
                      <SectionLabel>CONFIRMED INPUT</SectionLabel>
                      <h3>{decision.trip.flight_number}</h3>
                    </div>
                    <button type="button" onClick={() => setEditing(true)}>
                      编辑
                    </button>
                  </div>
                  <dl>
                    <div>
                      <dt>
                        <CalendarDays size={15} />
                        起飞
                      </dt>
                      <dd>{formatDateTime(decision.trip.scheduled_departure)}</dd>
                    </div>
                    <div>
                      <dt>
                        <MapPin size={15} />
                        机场
                      </dt>
                      <dd>
                        {decision.trip.departure_airport} {decision.trip.terminal}
                      </dd>
                    </div>
                    <div>
                      <dt>
                        <Navigation size={15} />
                        出发地
                      </dt>
                      <dd>{decision.trip.departure_place}</dd>
                    </div>
                    <div>
                      <dt>
                        <FileText size={15} />
                        行程来源
                      </dt>
                      <dd>{decision.trip.itinerary_source}</dd>
                    </div>
                    <div>
                      <dt>
                        <TimerReset size={15} />
                        总预算
                      </dt>
                      <dd>{totalPreparation} 分钟</dd>
                    </div>
                  </dl>
                  <div className="coverage-line">
                    <span>{decision.context.data_scope}</span>
                    <span>{decision.context.missing_sources.length} 类实时来源缺口</span>
                  </div>
                </aside>
              </div>

              <div className="context-grid">
                <article>
                  <Plane size={19} />
                  <span>航班时间窗</span>
                  <strong>值机截止 {formatTime(decision.context.flight.checkin_close_at)}</strong>
                  <small>
                    登机 {formatTime(decision.context.flight.boarding_start_at)} ·{" "}
                    {decision.context.flight.gate ?? "登机口待定"}
                  </small>
                </article>
                <article>
                  <Clock3 size={19} />
                  <span>机场流程</span>
                  <strong>
                    安检 {decision.context.airport.security_minutes} · 步行{" "}
                    {decision.context.airport.walking_minutes} 分钟
                  </strong>
                  <small>
                    距离约 {decision.context.airport.gate_distance_meters ?? "待确认"} 米
                  </small>
                </article>
                <article>
                  <Route size={19} />
                  <span>驾车道路时间</span>
                  <strong>
                    P50 {decision.context.route.p50_minutes} · P90{" "}
                    {decision.context.route.p90_minutes} 分钟
                  </strong>
                  <small>
                    {decision.context.route.metadata.source_name}
                    {decision.context.route.distance_km
                      ? ` · ${decision.context.route.distance_km} km`
                      : ""}
                    {" · "}
                    {congestionLabels[decision.context.route.congestion_level]}
                  </small>
                </article>
                <article>
                  <CloudRain size={19} />
                  <span>机场天气</span>
                  <strong>{decision.context.weather.summary}</strong>
                  <small>增加 {decision.context.weather.buffer_minutes} 分钟缓冲</small>
                </article>
                {decision.context.flight_telemetry && (
                  <article className="live-context">
                    <Plane size={19} />
                    <span>ADS-B 实时遥测</span>
                    <strong>
                      {decision.context.flight_telemetry.callsign} ·{" "}
                      {decision.context.flight_telemetry.state}
                    </strong>
                    <small>
                      最近信号 {formatTime(decision.context.flight_telemetry.last_contact_at)}
                      {decision.context.flight_telemetry.groundspeed_kph
                        ? ` · ${Math.round(decision.context.flight_telemetry.groundspeed_kph)} km/h`
                        : ""}
                    </small>
                  </article>
                )}
                {decision.context.aviation_weather && (
                  <article className="live-context">
                    <CloudRain size={19} />
                    <span>机场 METAR 实况</span>
                    <strong>
                      {decision.context.aviation_weather.station_icao} ·{" "}
                      {decision.context.aviation_weather.flight_category}
                    </strong>
                    <small title={decision.context.aviation_weather.raw_metar}>
                      观测 {formatTime(decision.context.aviation_weather.observed_at)} ·{" "}
                      {decision.context.aviation_weather.temperature_c ?? "—"}°C
                    </small>
                  </article>
                )}
              </div>
              {decision.context.warnings.length > 0 && (
                <output className="source-warnings">
                  {decision.context.warnings.map((warning) => (
                    <span key={warning}>
                      <CircleAlert size={14} /> {warning}
                    </span>
                  ))}
                </output>
              )}
              {showBjtuDutJourney && decision.trip.flight_number === "CA8908" && (
                <article className="complete-journey-card">
                  <div className="complete-journey-head">
                    <div>
                      <SectionLabel>COMPLETE JOURNEY</SectionLabel>
                      <h3>北京交通大学 → 大连理工大学完整旅程</h3>
                    </div>
                    <span>2026-07-27 已验证测试</span>
                  </div>
                  <div className="journey-steps">
                    <div>
                      <b>{formatTime(decision.decision.recommended_leave_at)}</b>
                      <span>离开北京交通大学</span>
                    </div>
                    <div>
                      <b>{formatTime(decision.decision.target_terminal_arrival)}</b>
                      <span>到达首都机场 T3</span>
                    </div>
                    <div>
                      <b>21:50</b>
                      <span>CA8908 计划起飞</span>
                    </div>
                    <div>
                      <b>23:05</b>
                      <span>计划到达大连机场</span>
                    </div>
                    <div>
                      <b>00:43–00:58</b>
                      <span>预计到达大连理工大学凌水校区</span>
                    </div>
                  </div>
                  <div className="journey-warning">
                    <CircleAlert size={17} />
                    <p>
                      如果你的意思是“21:00 才离开北京交通大学”，本系统测试结论是高风险不可行；
                      这里展示的是乘坐 21:50 航班所需的更早离校时间。
                    </p>
                  </div>
                  <p className="journey-note">
                    大连落地后按 23:35–23:50 完成下机和提取行李、12 分钟接驾、测试时道路 P90 56
                    分钟估算。航班时刻与最后一段道路需在出发当天重新确认。
                  </p>
                  <a
                    className="confirm-external"
                    href="https://uri.amap.com/navigation?from=121.542585%2C38.964154%2C%E5%A4%A7%E8%BF%9E%E5%91%A8%E6%B0%B4%E5%AD%90%E5%9B%BD%E9%99%85%E6%9C%BA%E5%9C%BA&to=121.525200%2C38.883283%2C%E5%A4%A7%E8%BF%9E%E7%90%86%E5%B7%A5%E5%A4%A7%E5%AD%A6%E5%87%8C%E6%B0%B4%E6%A0%A1%E5%8C%BA&mode=car&policy=1&src=mobility-management-agent&coordinate=gaode&callnative=1"
                    target="_blank"
                    rel="noreferrer"
                  >
                    查看大连机场到大连理工高德路线 <ArrowRight size={15} />
                  </a>
                </article>
              )}
            </>
          )}
        </section>

        {decision && (
          <section className="evidence-section">
            <div className="section-heading evidence-heading">
              <div>
                <SectionLabel>WHY THIS TIME</SectionLabel>
                <h2>每一分钟都有依据</h2>
              </div>
              <p>事实、配置、派生计算与缺失来源分开呈现。</p>
            </div>

            <div className="component-strip">
              {decision.decision.components.map((component) => (
                <div key={component.key}>
                  <span>{component.label}</span>
                  <strong>{component.minutes}</strong>
                  <small>分钟</small>
                </div>
              ))}
            </div>

            <div className="evidence-grid">
              {decision.evidence.map((item) => (
                <article className="evidence-card" key={item.evidence_id}>
                  <div className="evidence-icon">
                    <Database size={20} />
                  </div>
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                  <small>{item.source}</small>
                  {item.source_url && (
                    <a
                      className="evidence-link"
                      href={item.source_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      查看来源原文 <ArrowRight size={13} />
                    </a>
                  )}
                  <div className="evidence-meta">
                    <span>{item.status}</span>
                    <span>{Math.round(item.confidence * 100)}%</span>
                    <span>{item.completeness}</span>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {decision && (
          <section className="workflow-section" id={actionSectionId}>
            <div className="section-heading">
              <div>
                <SectionLabel>REMIND & ACT</SectionLabel>
                <h2>提醒与叫车，始终由你确认</h2>
              </div>
              <p>Agent 只生成可检查的提案，不会自动下单或付款。</p>
            </div>
            <div className="workflow-grid">
              <article className="workflow-card">
                <BellRing size={24} />
                <h3>T-24 出发提醒</h3>
                <p>生成日历提醒，内容包含建议时间、机场到达目标和叫车询问。</p>
                <button
                  type="button"
                  disabled={workflowBusy === "reminder"}
                  onClick={() => void buildReminder()}
                >
                  {reminder ? "重新生成提醒" : "预览提醒"}
                </button>
                {reminder && (
                  <div className="workflow-result">
                    <strong>{formatDateTime(reminder.remind_at)}</strong>
                    <span>{reminder.message}</span>
                    <button
                      type="button"
                      onClick={() =>
                        download(
                          `${decision.trip.flight_number}-行前提醒.ics`,
                          reminder.calendar_ics,
                          "text/calendar;charset=utf-8",
                        )
                      }
                    >
                      下载日历提醒
                    </button>
                  </div>
                )}
              </article>

              <article className="workflow-card">
                <MapPinned size={24} />
                <h3>地图与叫车入口</h3>
                <p>先展示出发时间和目的地，再由你点击打开高德地图。</p>
                <button
                  type="button"
                  disabled={workflowBusy === "action"}
                  onClick={() => void buildAction()}
                >
                  {actionProposal ? "更新操作提案" : "生成操作提案"}
                </button>
                {actionProposal && (
                  <div className="workflow-result">
                    {Object.entries(actionProposal.parameters_preview).map(([key, value]) => (
                      <span key={key}>
                        <b>{key}：</b>
                        {value}
                      </span>
                    ))}
                    <a
                      className="confirm-external"
                      href={actionProposal.deep_link}
                      target="_blank"
                      rel="noreferrer"
                    >
                      确认并打开官方地图 <ArrowRight size={15} />
                    </a>
                  </div>
                )}
              </article>

              <article className="workflow-card question-card">
                <MessageCircleQuestion size={24} />
                <h3>证据受限问答</h3>
                <p>回答只能引用本次决策证据；证据没有覆盖时会明确说明。</p>
                <form onSubmit={submitQuestion}>
                  <input
                    value={question}
                    onChange={(event) => setQuestion(event.target.value)}
                    placeholder="例如：天气和施工分别增加了多少时间？"
                  />
                  <button type="submit" disabled={workflowBusy === "question"}>
                    询问
                  </button>
                </form>
                {answer && (
                  <div className="workflow-result answer-result">
                    <strong>{answer.answer}</strong>
                    <span>引用：{answer.cited_evidence_ids.join("、")}</span>
                    <span>Provider：{answer.provider}</span>
                  </div>
                )}
              </article>
            </div>
          </section>
        )}

        <section className="sources-section" id={sourcesSectionId}>
          <div className="section-heading">
            <div>
              <SectionLabel>SOURCE REGISTRY</SectionLabel>
              <h2>每个来源的状态都可见</h2>
            </div>
            <p>未配置的商业来源不会被模型记忆替代。</p>
          </div>
          <div className="source-grid">
            {sources.map((source) => (
              <article key={source.source_id}>
                <div className="source-head">
                  <span>{source.category}</span>
                  <b className={`source-mode mode-${source.mode}`}>
                    {sourceModeLabels[source.mode]}
                  </b>
                </div>
                <h3>{source.label}</h3>
                <p>{source.detail}</p>
                <small>
                  {source.requires_secret ? "服务端凭据" : "无客户端密钥"} ·{" "}
                  {source.freshness_minutes
                    ? `TTL ${source.freshness_minutes} 分钟`
                    : "版本/能力状态"}
                </small>
              </article>
            ))}
          </div>
        </section>

        <section className="boundary-section">
          <div className="boundary-copy">
            <SectionLabel>PRIVACY & GOVERNANCE</SectionLabel>
            <h2>模型负责理解，代码负责决定</h2>
            <p>
              当前服务端不持久化行程、地址、OCR 图片或问答。地图、模型和提醒均有独立同意门禁；
              第三方 App 只接受用户主动导入或官方授权来源。
            </p>
          </div>
          <div className="privacy-actions">
            <button
              type="button"
              disabled={workflowBusy === "privacy"}
              onClick={() => void exportPrivacy()}
            >
              导出数据说明
            </button>
            <button
              className="danger-outline"
              type="button"
              disabled={workflowBusy === "privacy"}
              onClick={() => void clearSession()}
            >
              清空本次会话
            </button>
            {privacyMessage && <span>{privacyMessage}</span>}
          </div>
        </section>
      </main>

      <footer>
        <div className="brand footer-brand">
          <span className="brand-mark">
            <Navigation size={18} />
          </span>
          <span>
            <strong>行前</strong>
            <small>MOBILITY MANAGEMENT AGENT</small>
          </span>
        </div>
        <p>版本 0.4.1 · Live evidence · No automatic booking or payment</p>
      </footer>

      {editing && trip && (
        <div className="modal-backdrop" role="presentation">
          <div
            className="modal wide-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={editTripTitleId}
          >
            <div className="modal-head">
              <div>
                <SectionLabel>CONFIRM TRIP</SectionLabel>
                <h2 id={editTripTitleId}>逐项确认行程与偏好</h2>
              </div>
              <button type="button" onClick={() => setEditing(false)}>
                关闭
              </button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <label>
                  航班号
                  <input
                    required
                    value={trip.flight_number}
                    onChange={(event) =>
                      setTrip({ ...trip, flight_number: event.target.value.toUpperCase() })
                    }
                  />
                </label>
                <label>
                  计划起飞
                  <input
                    required
                    type="datetime-local"
                    value={toLocalInput(trip.scheduled_departure)}
                    onChange={(event) =>
                      setTrip({
                        ...trip,
                        scheduled_departure: fromLocalInput(event.target.value),
                      })
                    }
                  />
                </label>
              </div>
              <div className="form-row">
                <label>
                  出发机场
                  <input
                    required
                    maxLength={3}
                    value={trip.departure_airport}
                    onChange={(event) =>
                      setTrip({
                        ...trip,
                        departure_airport: event.target.value.toUpperCase(),
                      })
                    }
                  />
                </label>
                <label>
                  目的机场
                  <input
                    maxLength={3}
                    value={trip.destination_airport ?? ""}
                    onChange={(event) =>
                      setTrip({
                        ...trip,
                        destination_airport: event.target.value
                          ? event.target.value.toUpperCase()
                          : null,
                      })
                    }
                  />
                </label>
                <label>
                  航站楼
                  <input
                    required
                    value={trip.terminal}
                    onChange={(event) => setTrip({ ...trip, terminal: event.target.value })}
                  />
                </label>
              </div>
              <label>
                出发地
                <input
                  required
                  value={trip.departure_place}
                  onChange={(event) => setTrip({ ...trip, departure_place: event.target.value })}
                />
                <small>服务端默认不持久化；启用地图前请确认是否愿意发送坐标。</small>
              </label>
              <div className="form-row">
                <label>
                  经度（可选）
                  <input
                    type="number"
                    min="-180"
                    max="180"
                    step="0.000001"
                    value={trip.departure_coordinates?.longitude ?? ""}
                    onChange={(event) => {
                      const value = event.target.value
                      setTrip({
                        ...trip,
                        departure_coordinates: value
                          ? {
                              longitude: Number(value),
                              latitude: trip.departure_coordinates?.latitude ?? 39.9,
                            }
                          : null,
                      })
                    }}
                  />
                </label>
                <label>
                  纬度（可选）
                  <input
                    type="number"
                    min="-90"
                    max="90"
                    step="0.000001"
                    value={trip.departure_coordinates?.latitude ?? ""}
                    onChange={(event) => {
                      const value = event.target.value
                      setTrip({
                        ...trip,
                        departure_coordinates: value
                          ? {
                              longitude: trip.departure_coordinates?.longitude ?? 116.4,
                              latitude: Number(value),
                            }
                          : null,
                      })
                    }}
                  />
                </label>
              </div>
              <label>
                已知活动、施工、封路或事故（每行一条，最多 5 条）
                <textarea
                  rows={3}
                  value={(trip.user_disruption_notes ?? []).join("\n")}
                  onChange={(event) =>
                    setTrip({
                      ...trip,
                      user_disruption_notes: event.target.value
                        .split("\n")
                        .map((item) => item.trim())
                        .filter(Boolean)
                        .slice(0, 5),
                    })
                  }
                />
              </label>
              <div className="form-row">
                <label>
                  风险偏好
                  <select
                    value={trip.risk_profile}
                    onChange={(event) =>
                      setTrip({
                        ...trip,
                        risk_profile: event.target.value as TripInput["risk_profile"],
                      })
                    }
                  >
                    <option value="standard">标准</option>
                    <option value="cautious">稳妥</option>
                    <option value="very_cautious">非常稳妥</option>
                  </select>
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={trip.checked_baggage}
                    onChange={(event) =>
                      setTrip({ ...trip, checked_baggage: event.target.checked })
                    }
                  />
                  <span>需要托运行李</span>
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={trip.accessibility_assistance}
                    onChange={(event) =>
                      setTrip({ ...trip, accessibility_assistance: event.target.checked })
                    }
                  />
                  <span>需要无障碍协助</span>
                </label>
              </div>
              <div className="consent-box">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={trip.live_data_consent}
                    onChange={(event) =>
                      setTrip({ ...trip, live_data_consent: event.target.checked })
                    }
                  />
                  <span>
                    允许本次查询公开 ADS-B/获权航班来源；提供坐标后，在预计离家前 3
                    小时内允许服务端调用高德实时驾车路线
                  </span>
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={trip.model_egress_consent}
                    onChange={(event) =>
                      setTrip({ ...trip, model_egress_consent: event.target.checked })
                    }
                  />
                  <span>允许把派生证据发送给已批准模型用于本次解释</span>
                </label>
              </div>
              <button className="primary-action modal-submit" type="submit">
                确认并生成建议
                <ArrowRight size={17} />
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
