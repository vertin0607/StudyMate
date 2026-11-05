import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// 开发时把 /api 转到本机 FastAPI。浏览器始终访问当前页面的 /api，局域网设备不会去请求自己的 127.0.0.1。
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // 组员通过这台电脑的局域网 IP 打开页面。仅用于可信局域网。
    allowedHosts: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        timeout: 180_000,
      },
    },
  },
});
