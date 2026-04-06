import fs from "node:fs";
import path from "node:path";
import type { Plugin } from "vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const SNAPSHOT_ROUTE = "/site_data/current";
const SNAPSHOT_SOURCE = path.resolve(__dirname, "../site_data/current");

function contentTypeFor(filePath: string): string {
  if (filePath.endsWith(".json")) {
    return "application/json; charset=utf-8";
  }
  if (filePath.endsWith(".html")) {
    return "text/html; charset=utf-8";
  }
  if (filePath.endsWith(".css")) {
    return "text/css; charset=utf-8";
  }
  if (filePath.endsWith(".js")) {
    return "application/javascript; charset=utf-8";
  }
  return "text/plain; charset=utf-8";
}

function snapshotPlugin(): Plugin {
  return {
    name: "snapshot-plugin",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const requestUrl = req.url || "";
        if (!requestUrl.startsWith(SNAPSHOT_ROUTE)) {
          next();
          return;
        }

        const relativePath = requestUrl.slice(SNAPSHOT_ROUTE.length).replace(/^\/+/, "");
        const targetPath = path.resolve(SNAPSHOT_SOURCE, relativePath || "manifest.json");

        if (!targetPath.startsWith(SNAPSHOT_SOURCE) || !fs.existsSync(targetPath) || fs.statSync(targetPath).isDirectory()) {
          next();
          return;
        }

        res.statusCode = 200;
        res.setHeader("Content-Type", contentTypeFor(targetPath));
        res.end(fs.readFileSync(targetPath));
      });
    },
    writeBundle(outputOptions) {
      const outputDir = outputOptions.dir ? path.resolve(outputOptions.dir) : path.resolve(__dirname, "dist");
      const targetDir = path.join(outputDir, "site_data", "current");

      if (!fs.existsSync(SNAPSHOT_SOURCE)) {
        return;
      }

      fs.rmSync(targetDir, { recursive: true, force: true });
      fs.mkdirSync(path.dirname(targetDir), { recursive: true });
      fs.cpSync(SNAPSHOT_SOURCE, targetDir, { recursive: true });
    },
  };
}

export default defineConfig({
  plugins: [react(), snapshotPlugin()],
  test: {
    environment: "jsdom",
    setupFiles: "./src/testSetup.ts",
  },
});
