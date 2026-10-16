import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  base: "/",
  plugins: [react()],
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:7342", changeOrigin: false } },
  },
  build: {
    outDir: fileURLToPath(new URL("../src/career/server/static", import.meta.url)),
    emptyOutDir: true,
    chunkSizeWarningLimit: 600,
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
  },
});
