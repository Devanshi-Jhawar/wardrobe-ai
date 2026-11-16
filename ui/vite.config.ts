import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the UI calls /api/..., which Vite forwards to the agent
// (the API gateway) on port 8000. In Docker, nginx does the same job.
const AGENT = process.env.AGENT_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: AGENT, changeOrigin: true, rewrite: (p) => p.replace(/^\/api/, "") },
    },
  },
});
