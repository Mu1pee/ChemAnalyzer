import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";

const pkg = JSON.parse(
  readFileSync(new URL("./package.json", import.meta.url), "utf8")
) as { version: string };

export default defineConfig({
  plugins: [react()],
  // Версия приложения берётся из package.json — не дублируется в коде.
  define: { __APP_VERSION__: JSON.stringify(pkg.version) },
  // Интерфейс раздаёт backend из корня (http://127.0.0.1:<порт>/), поэтому
  // пути к ресурсам Ketcher/Vite абсолютные от "/". Не используйте file://.
  base: "/",
  server: {
    port: 5173,
    strictPort: true // npm run dev (Electron) ожидает именно этот порт
  },
  build: {
    // Ketcher и 3Dmol — крупные пакеты, предупреждение о размере не актуально.
    chunkSizeWarningLimit: 6000
  }
});
