import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API + WebSocket calls to the Xplogent backend on :8765.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:8765",
      "/config": "http://localhost:8765",
      "/skills": "http://localhost:8765",
      "/memory": "http://localhost:8765",
      "/ws": { target: "ws://localhost:8765", ws: true },
    },
  },
});
