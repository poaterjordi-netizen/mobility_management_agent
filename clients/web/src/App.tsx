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
  const [intakeText, setIntakeText] = useState(
    "【携程行程通知示例】CA1832 杭州萧山机场 T4 → 北京首都机场，2026/8/1 09:20 起飞",
  )
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [candidate, setCandidate] = useState<TripCandidate | null>(null)
  const [intakeBusy, setIntakeBusy] = useState(false)
  const [intakeError, setIntakeError] = useState("")

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
      .then(async ([demoTrip, serviceCapabilities, sourceStatuses]) => {
        if (!active) return
        setTrip(demoTrip)
        setCapabilities(serviceCapabilities)
        setSources(sourceStatuses)
        await calculate(demoTrip)
      })
      .catch((requestError) => {
        if (!active) return
        setError(requestError instanceof Error ? requestError.message : "服务连接失败")
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [calculate])

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
    setIntakeBusy(true)
    setIntakeError("")
    setCandidate(null)
    try {
      const parsed =
        intakeMode === "image"
          ? imageFile
            ? await parseTripImage(imageFile, {
                departure_place: trip.departure_place,
                checked_baggage: trip.checked_baggage,
                risk_profile: trip.risk_profile,
              })
            : null
          : await parseTripCandidate({
              source_type: intakeMode,
              content: intakeText,
              departure_place: trip.departure_place,
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
      flight_number: candidate.flight_number ?? trip.flight_number,
      departure_airport: candidate.departure_airport ?? trip.departure_airport,
      destination_airport: candidate.destination_airport ?? trip.destination_airport,
      terminal: candidate.terminal ?? trip.terminal,
      scheduled_departure: candidate.scheduled_departure ?? trip.scheduled_departure,
      departure_place: candidate.departure_place,
      checked_baggage: candidate.checked_baggage,
      risk_profile: candidate.risk_profile,
      itinerary_source: candidate.itinerary_source,
    })
    setCandidate(null)
    setEditing(true)
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
                导入我的行程
                <ArrowRight size={17} />
              </a>
              <a className="text-action" href={`#${decisionSectionId}`}>
                查看当前建议
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
              <span>下一段旅程</span>
              <strong>{trip?.flight_number ?? "待导入"}</strong>
              <div>
                <b>{trip?.departure_airport ?? "—"}</b>
                <ArrowRight size={18} />
                <b>{trip?.destination_airport ?? "—"}</b>
              </div>
              <small>{trip ? formatDate(trip.scheduled_departure) : "尚未确认"}</small>
            </div>
            <Plane className="orbit-plane" size={34} />
          </div>
        </section>

        <section className="intake-section" id={intakeSectionId}>
          <div className="section-heading">
            <div>
              <SectionLabel>TRIP UNDERSTANDING</SectionLabel>
              <h2>把行程交给 Agent 整理</h2>
            </div>
            <p>
              可直接粘贴你自己的携程、航旅纵横或航司通知；原文只用于本次解析，字段确认后才计算。
            </p>
          </div>
          <div className="intake-layout">
            <article className="intake-card">
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
                    onChange={(event) => setIntakeText(event.target.value)}
                    rows={7}
                    placeholder={
                      intakeMode === "ics"
                        ? "BEGIN:VCALENDAR…"
                        : "例如：CA1832，杭州萧山 T4，2026/8/1 09:20 起飞"
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
                解析为待确认行程
              </button>
              {intakeError && <div className="inline-error">{intakeError}</div>}
            </article>

            <article className="candidate-card">
              <SectionLabel>CONFIRMATION REQUIRED</SectionLabel>
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
                    带入表单并逐项确认 <ArrowRight size={16} />
                  </button>
                </>
              ) : (
                <div className="candidate-empty">
                  <ShieldCheck size={30} />
                  <strong>解析结果不会直接生效</strong>
                  <span>航班号、日期、机场、航站楼和时间都要经过确认。</span>
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
          ) : loading || !decision ? (
            <LoadingCard />
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
