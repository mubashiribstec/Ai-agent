import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API + WebSocket calls to the Xplogent backend on :8765.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: Object.fromEntries(
      [
        "/health", "/config", "/skills", "/memory", "/tools", "/roles",
        "/secrets", "/models", "/sessions", "/guide", "/update",
        "/orchestrate", "/runs", "/agents", "/messages", "/run",
      ].map((p) => [p, "http://localhost:8765"]).concat([
        ["/ws", { target: "ws://localhost:8765", ws: true } as any],
      ] as any)
    ),
  },
});
