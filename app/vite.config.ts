/// <reference types="vitest/config" />
import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  build: { target: "es2022", chunkSizeWarningLimit: 1300 /* maplibre-gl is bundled for offline use */ },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
