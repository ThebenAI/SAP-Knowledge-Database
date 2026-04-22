import { defineConfig, type ProxyOptions } from "vite";
import react from "@vitejs/plugin-react";

const apiProxy: ProxyOptions = {
  target: "http://127.0.0.1:8000",
  changeOrigin: true,
  configure: (proxy) => {
    proxy.on("proxyReq", (_proxyReq, req) => {
      console.info(`[vite-proxy] ${req.method ?? "UNKNOWN"} ${req.url ?? ""}`);
    });
    proxy.on("error", (err, req) => {
      console.error(`[vite-proxy] error on ${req.method ?? "UNKNOWN"} ${req.url ?? ""}:`, err);
    });
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": apiProxy,
    },
  },
});