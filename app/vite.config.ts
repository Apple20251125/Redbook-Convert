import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig, loadEnv } from "vite"
import { inspectAttr } from 'kimi-plugin-inspect-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 后端地址可用 VITE_API_PROXY_TARGET 覆盖（例如后端跑在 8001 时写进 .env.local）
  const env = loadEnv(mode, process.cwd(), "")
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8000'

  return {
    base: './',
    plugins: [inspectAttr(), react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      // 监听所有网卡，IPv4(127.0.0.1) 与局域网均可访问
      host: true,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
