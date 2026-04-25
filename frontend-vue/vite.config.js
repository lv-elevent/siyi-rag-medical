import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    strictPort: true,
    proxy: {
      "/auth": "http://127.0.0.1:8000",
      "/chat": "http://127.0.0.1:8000",
      "/chat-stream": "http://127.0.0.1:8000",
      "/knowledge": "http://127.0.0.1:8000",
      "/upload": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000"
    }
  }
});
