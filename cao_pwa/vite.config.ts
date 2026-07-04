/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// L2 standalone PWA. Unlike cao_mcp_apps (single-file iframe-bundled),
// this PWA is deployed at its own origin (Vercel, internal Nginx,
// GitHub Pages, etc.) and ships as a normal multi-asset Vite build.
//
// Sibling RFC: docs/rfc/cao-agui-l2-dashboard-2026-05-11-v1.md.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    target: "es2020",
    minify: "esbuild",
  },
  server: {
    host: "localhost",
    port: 5174, // 5173 is reserved by web/; pick the next slot
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
