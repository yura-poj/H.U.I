import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  publicDir: "static",
  server: {
    port: 5173,
  },
  test: {
    environment: "jsdom",
  },
});
