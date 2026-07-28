import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // Пакет объявляет типы через export =, но его ESM-сборка отдаёт
      // только именованный экспорт. Берём CJS-сборку, чтобы рантайм и
      // типы описывали одно и то же.
      "qrcode-generator": "qrcode-generator/dist/qrcode.js",
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
  },
});
