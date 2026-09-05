import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

// The development server needs a WebSocket back to itself for hot reloads.
// The built file connects nowhere, and its policy says so.
const DEVELOPMENT_CONNECT_SRC =
  "connect-src 'self' ws://localhost:* ws://127.0.0.1:*";

function releaseContentSecurityPolicy(): Plugin {
  return {
    name: "traigent:release-content-security-policy",
    apply: "build",
    transformIndexHtml(html) {
      if (!html.includes(DEVELOPMENT_CONNECT_SRC)) {
        throw new Error(
          "index.html no longer carries the development connect-src this build expected to replace",
        );
      }
      return html.replace(DEVELOPMENT_CONNECT_SRC, "connect-src 'none'");
    },
  };
}

export default defineConfig({
  base: "./",
  plugins: [react(), viteSingleFile(), releaseContentSecurityPolicy()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    cssCodeSplit: false,
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
  },
});
