import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    /*
     * Витрину и оплату отдаёт бот, а в бою до него доводит nginx (см.
     * nginx.conf). Здесь тот же путь повторён для разработки: иначе
     * страница покупки локально не видит ни тарифов, ни платежей, и
     * проверить её можно было бы только выкатив на прод.
     */
    proxy: {
      "/shop": {
        target: "https://vpanfibot.ru",
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/shop/, "/cabinet/landing"),
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
  },
});
