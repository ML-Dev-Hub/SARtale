/// <reference types="vitest/config" />
import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  build: { target: "es2022", chunkSizeWarningLimit: 1300 /* maplibre-gl is bundled for offline use */ },
  server: { proxy: { "/api": "http://127.0.0.1:8787" } },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
