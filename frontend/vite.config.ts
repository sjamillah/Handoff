import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * In development the API runs on :8000. Requests to /api are forwarded there
 * without the prefix, as nginx does in production, so the browser only ever
 * talks to one origin and the session cookie needs no CORS.
 */
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
