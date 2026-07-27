import createClient from "openapi-fetch"
import type { components, paths } from "./api-schema"

const baseUrl = (import.meta.env.VITE_API_BASE as string | undefined) ?? ""

export const api = createClient<paths>({ baseUrl })

type TripInput = components["schemas"]["TripInput"]
type DecisionResponse = components["schemas"]["DecisionResponse"]

function message(error: unknown, fallback: string) {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail?: unknown }).detail
    if (typeof detail === "string") return detail
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : "参数错误",
        )
        .join("；")
    }
  }
  return fallback
}

export async function getDemoTrip() {
  const { data, error } = await api.GET("/api/v1/demo/trip")
  if (error || !data) throw new Error(message(error, "无法载入示例行程"))
  return data
}

export async function getCapabilities() {
  const { data, error } = await api.GET("/api/v1/capabilities")
  if (error || !data) throw new Error(message(error, "无法读取服务能力"))
  return data
}

export async function getSources() {
  const { data, error } = await api.GET("/api/v1/sources")
  if (error || !data) throw new Error(message(error, "无法读取数据源状态"))
  return data
}

export async function parseTripCandidate(body: components["schemas"]["TripParseRequest"]) {
  const { data, error } = await api.POST("/api/v1/trips/candidates", { body })
  if (error || !data) throw new Error(message(error, "无法解析行程内容"))
  return data
}

export async function parseTripImage(
  image: File,
  defaults: {
    departure_place: string
    checked_baggage: boolean
    risk_profile: TripInput["risk_profile"]
  },
) {
  const form = new FormData()
  form.append("image", image)
  form.append("departure_place", defaults.departure_place)
  form.append("checked_baggage", String(defaults.checked_baggage))
  form.append("risk_profile", defaults.risk_profile)
  const response = await fetch(`${baseUrl}/api/v1/trips/candidates/image`, {
    method: "POST",
    body: form,
  })
  const payload = await response.json()
  if (!response.ok) throw new Error(message(payload, "截图 OCR 失败"))
  return payload as components["schemas"]["TripCandidate"]
}

export async function previewDecision(trip: TripInput) {
  const { data, error } = await api.POST("/api/v1/decisions/preview", {
    body: trip,
  })
  if (error || !data) {
    throw new Error(message(error, "暂时无法生成出发建议，请检查输入或服务状态"))
  }
  return data
}

export async function previewReminder(decision: DecisionResponse, leadHours = 24) {
  const { data, error } = await api.POST("/api/v1/reminders/preview", {
    body: {
      trip: decision.trip,
      decision: decision.decision,
      lead_hours: leadHours,
    },
  })
  if (error || !data) throw new Error(message(error, "无法生成提醒预览"))
  return data
}

export async function proposeAction(
  decision: DecisionResponse,
  actionType: "open_map" | "open_ride_hailing",
) {
  const { data, error } = await api.POST("/api/v1/action-proposals", {
    body: {
      trip: decision.trip,
      decision: decision.decision,
      action_type: actionType,
    },
  })
  if (error || !data) throw new Error(message(error, "无法生成地图操作提案"))
  return data
}

export async function askAssistant(question: string, decision: DecisionResponse) {
  const { data, error } = await api.POST("/api/v1/assistant/questions", {
    body: { question, decision },
  })
  if (error || !data) throw new Error(message(error, "证据问答暂时不可用"))
  return data
}

export async function getPrivacyExport() {
  const { data, error } = await api.GET("/api/v1/privacy/export")
  if (error || !data) throw new Error(message(error, "无法生成隐私导出"))
  return data
}

export async function deleteServerSession() {
  const { data, error } = await api.DELETE("/api/v1/privacy/session")
  if (error || !data) throw new Error(message(error, "无法清理服务端会话"))
  return data
}
