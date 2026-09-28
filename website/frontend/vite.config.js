import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/static/dist/",
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: "assets/dashboard.js",
        chunkFileNames: "assets/[name].js",
        assetFileNames: "assets/dashboard[extname]",
      },
    },
  },
  server: {
    proxy: { "/api": "http://127.0.0.1:9090", "/auth": "http://127.0.0.1:9090" },
  },
});