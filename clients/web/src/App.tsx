import {
  ArrowRight,
  BadgeCheck,
  CalendarDays,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  CloudSun,
  MapPin,
  Navigation,
  Plane,
  RefreshCw,
  Route,
  ShieldCheck,
  Sparkles,
  TimerReset,
} from "lucide-react"
import { type FormEvent, useCallback, useEffect, useId, useMemo, useState } from "react"
import { getCapabilities, getDemoTrip, previewDecision } from "./api"
import type { components } from "./api-schema"

type TripInput = components["schemas"]["TripInput"]
type DecisionResponse = components["schemas"]["DecisionResponse"]
type Capabilities = components["schemas"]["CapabilitiesResponse"]

const riskLabels: Record<TripInput["risk_profile"], string> = {
  standard: "标准",
  cautious: "稳妥",
  very_cautious: "非常稳妥",
}

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

function toLocalInput(value: string) {
  const date = new Date(value)
  const chinaTime = new Date(date.getTime() + 8 * 60 * 60 * 1000)
  return chinaTime.toISOString().slice(0, 16)
}

function fromLocalInput(value: string) {
  return `${value}:00+08:00`
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
  const editTripTitleId = useId()
  const [trip, setTrip] = useState<TripInput | null>(null)
  const [decision, setDecision] = useState<DecisionResponse | null>(null)
  const [capabilities, setCapabilities] = useState<Capabilities | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [editing, setEditing] = useState(false)

  const calculate = useCallback(async (nextTrip: TripInput) => {
    setLoading(true)
    setError("")
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
    Promise.all([getDemoTrip(), getCapabilities()])
      .then(async ([demoTrip, serviceCapabilities]) => {
        if (!active) return
        setTrip(demoTrip)
        setCapabilities(serviceCapabilities)
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
        <div className="status-pill">
          <span className="status-dot" />
          合成数据 · 框架版
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-copy">
            <div className="eyebrow">
              <Sparkles size={14} />
              在你迟到之前，把分散信息变成一个决定
            </div>
            <h1>
              明天去机场，
              <br />
              <span>应该几点出发？</span>
            </h1>
            <p>
              行前把航班、机场流程、道路风险和你的偏好放进一条可核验的时间线。
              这一版只使用合成数据，用来验证产品和工程框架。
            </p>
            <div className="hero-actions">
              <a className="primary-action" href={`#${decisionSectionId}`}>
                查看合成建议
                <ArrowRight size={17} />
              </a>
              <button className="text-action" type="button" onClick={() => setEditing(true)}>
                调整行程
                <ChevronRight size={16} />
              </button>
            </div>
          </div>

          <div className="flight-orbit" aria-hidden="true">
            <div className="orbit-ring ring-one" />
            <div className="orbit-ring ring-two" />
            <div className="orbit-card">
              <span>下一段旅程</span>
              <strong>{trip?.flight_number ?? "CA1234"}</strong>
              <div>
                <b>{trip?.departure_airport ?? "PEK"}</b>
                <ArrowRight size={18} />
                <b>SHA</b>
              </div>
              <small>{trip ? formatDate(trip.scheduled_departure) : "8月1日 周六"}</small>
            </div>
            <Plane className="orbit-plane" size={34} />
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
              重新计算
            </button>
          </div>

          {error ? (
            <div className="error-card" role="alert">
              <CircleAlert size={20} />
              <div>
                <strong>暂时无法生成建议</strong>
                <span>{error}</span>
              </div>
            </div>
          ) : loading || !decision ? (
            <LoadingCard />
          ) : (
            <div className="decision-grid">
              <article className="recommendation-card">
                <div className="recommendation-topline">
                  <span className="verified-badge">
                    <BadgeCheck size={16} />
                    确定性核验通过
                  </span>
                  <span className="risk-badge">{riskLabels[decision.trip.risk_profile]}方案</span>
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
                    <dd>
                      {formatDate(decision.trip.scheduled_departure)}{" "}
                      {formatTime(decision.trip.scheduled_departure)}
                    </dd>
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
                      <TimerReset size={15} />
                      预算
                    </dt>
                    <dd>{totalPreparation} 分钟</dd>
                  </div>
                </dl>
                <button className="ride-action" type="button" disabled>
                  <Navigation size={17} />
                  预约网约车（后续开放）
                </button>
              </aside>
            </div>
          )}
        </section>

        {decision && (
          <section className="evidence-section">
            <div className="section-heading evidence-heading">
              <div>
                <SectionLabel>WHY THIS TIME</SectionLabel>
                <h2>每一分钟都有依据</h2>
              </div>
              <p>事实、合成规则和派生结果分开呈现，不让模型补写实时信息。</p>
            </div>

            <div className="evidence-grid">
              {decision.evidence.slice(1).map((item, index) => {
                const icons = [Clock3, Route, Navigation, CloudSun]
                const Icon = icons[index] ?? ShieldCheck
                return (
                  <article className="evidence-card" key={item.evidence_id}>
                    <div className="evidence-icon">
                      <Icon size={20} />
                    </div>
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                    <small>{item.source}</small>
                  </article>
                )
              })}
            </div>
          </section>
        )}

        <section className="boundary-section">
          <div className="boundary-copy">
            <SectionLabel>GOVERNED BY DESIGN</SectionLabel>
            <h2>模型负责理解，代码负责决定</h2>
            <p>
              当前服务不保存行程，不连接真实航班或道路，也不会读取其他 App、自动叫车或付款。
              这些能力只有在数据授权、隐私和验收门禁通过后才会逐步加入。
            </p>
          </div>
          <div className="boundary-list">
            {(capabilities?.features ?? []).map((feature) => (
              <div key={feature}>
                <Check size={16} />
                {feature}
              </div>
            ))}
            {(capabilities?.blocked_actions ?? []).slice(0, 2).map((action) => (
              <div className="blocked" key={action}>
                <ShieldCheck size={16} />
                {action}
              </div>
            ))}
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
        <p>框架版本 0.1 · Synthetic data only · 结果不用于真实出行</p>
      </footer>

      {editing && trip && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby={editTripTitleId}>
            <div className="modal-head">
              <div>
                <SectionLabel>SYNTHETIC TRIP</SectionLabel>
                <h2 id={editTripTitleId}>调整合成行程</h2>
              </div>
              <button type="button" onClick={() => setEditing(false)}>
                关闭
              </button>
            </div>
            <form onSubmit={handleSubmit}>
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
                  航站楼
                  <input
                    required
                    value={trip.terminal}
                    onChange={(event) => setTrip({ ...trip, terminal: event.target.value })}
                  />
                </label>
              </div>
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
              <label>
                出发地（请继续使用合成地点）
                <input
                  required
                  value={trip.departure_place}
                  onChange={(event) => setTrip({ ...trip, departure_place: event.target.value })}
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
              </div>
              <button className="primary-action modal-submit" type="submit">
                生成新建议
                <ArrowRight size={17} />
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
