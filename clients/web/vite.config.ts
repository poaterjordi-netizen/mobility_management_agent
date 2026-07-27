import react from "@vitejs/plugin-react-swc"
import { defineConfig, loadEnv } from "vite"

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "")
  const devPort = Number(env.VITE_DEV_PORT || "5173")
  const proxyTarget = env.VITE_PROXY_TARGET || "http://127.0.0.1:8000"
  return {
    base: env.VITE_BASE_PATH || "/",
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: devPort,
      proxy: {
        "/api": proxyTarget,
        "/health": proxyTarget,
      },
    },
  }
})
