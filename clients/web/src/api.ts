import createClient from "openapi-fetch"
import type { paths } from "./api-schema"

const baseUrl = (import.meta.env.VITE_API_BASE as string | undefined) ?? ""

export const api = createClient<paths>({ baseUrl })

export async function getDemoTrip() {
  const { data, error } = await api.GET("/api/v1/demo/trip")
  if (error || !data) {
    throw new Error("无法载入合成示例行程")
  }
  return data
}

export async function getCapabilities() {
  const { data, error } = await api.GET("/api/v1/capabilities")
  if (error || !data) {
    throw new Error("无法读取服务能力")
  }
  return data
}

export async function previewDecision(
  trip: paths["/api/v1/decisions/preview"]["post"]["requestBody"]["content"]["application/json"],
) {
  const { data, error } = await api.POST("/api/v1/decisions/preview", {
    body: trip,
  })
  if (error || !data) {
    throw new Error("暂时无法生成出发建议，请检查输入或服务状态")
  }
  return data
}
