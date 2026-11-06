/// <reference types="vitest/config" />
import { copyFileSync, createReadStream, existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";
import { srtToVtt } from "./src/vtt";

const MEDIA = resolve(dirname(fileURLToPath(import.meta.url)), "../media");
const TYPES: Record<string, string> = { ".mp4": "video/mp4", ".jpg": "image/jpeg", ".vtt": "text/vtt; charset=utf-8" };

/**
 * The files the site serves under media/, by served name: each video and its poster (a source path to copy),
 * and its captions as WebVTT made from the .srt (the text itself).
 */
function mediaFiles(): Map<string, { path: string } | { text: string }> {
  const out = new Map<string, { path: string } | { text: string }>();
  if (!existsSync(MEDIA)) return out;
  for (const f of readdirSync(MEDIA)) {
    if (f.endsWith(".mp4")) out.set(f, { path: join(MEDIA, f) });
    if (f.endsWith(".srt")) out.set(f.replace(/\.srt$/, ".vtt"), { text: srtToVtt(readFileSync(join(MEDIA, f), "utf8")) });
  }
  const posters = join(MEDIA, "posters");
  if (existsSync(posters)) for (const f of readdirSync(posters)) if (f.endsWith(".jpg")) out.set(`posters/${f}`, { path: join(posters, f) });
  return out;
}

/** Serves ../media in dev and copies it into dist/media on build, so the videos are not kept twice in git. */
function sartaleMedia(): Plugin {
  let outDir = "dist";
  return {
    name: "sartale-media",
    configResolved(c) {
      outDir = resolve(c.root, c.build.outDir);
    },
    configureServer(server) {
      server.middlewares.use("/media/", (req, res, next) => {
        const name = decodeURIComponent((req.url ?? "").split("?")[0].replace(/^\//, ""));
        const file = mediaFiles().get(name);
        if (!file) return next();
        res.setHeader("Content-Type", TYPES[name.slice(name.lastIndexOf("."))] ?? "application/octet-stream");
        if ("text" in file) return void res.end(file.text);
        // Answer range requests, so the browser can seek in a video.
        const size = statSync(file.path).size;
        const m = /bytes=(\d*)-(\d*)/.exec(req.headers.range ?? "");
        const start = m?.[1] ? Number(m[1]) : 0;
        const end = m?.[2] ? Math.min(Number(m[2]), size - 1) : size - 1;
        res.setHeader("Accept-Ranges", "bytes");
        if (m) {
          res.statusCode = 206;
          res.setHeader("Content-Range", `bytes ${start}-${end}/${size}`);
        }
        res.setHeader("Content-Length", String(end - start + 1));
        createReadStream(file.path, { start, end }).pipe(res);
      });
    },
    writeBundle() {
      for (const [name, file] of mediaFiles()) {
        const dest = join(outDir, "media", name);
        mkdirSync(dirname(dest), { recursive: true });
        if ("text" in file) writeFileSync(dest, file.text);
        else copyFileSync(file.path, dest);
      }
    },
  };
}

export default defineConfig({
  base: "./",
  plugins: [sartaleMedia()],
  build: { target: "es2022", chunkSizeWarningLimit: 1300 /* maplibre-gl is bundled for offline use */ },
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
