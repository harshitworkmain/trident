import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

declare const process: { env: Record<string, string | undefined> };
const API = process.env.TRIDENT_API ?? 'http://localhost:8000';

interface Fs {
  readFileSync(path: string, enc: 'utf8'): string;
  writeFileSync(path: string, data: string): void;
  existsSync(path: string): boolean;
}

/**
 * Writes the app-shell precache list into dist/sw.js (copied from public/sw.js): index.html, the
 * hashed JS/CSS it references, the latin woff2 fonts those stylesheets use, the logo and the
 * manifest. Lazy staff chunks are cached on first use instead. The version is a hash of the list,
 * so every build that changes the shell installs a new worker and drops the old caches.
 */
function swPrecache(): Plugin {
  return {
    name: 'trident-sw-precache',
    apply: 'build',
    async writeBundle(opts) {
      // Node built-ins without @types/node: a non-literal specifier keeps tsc out of it.
      const fsId = 'node:fs';
      const fs = (await import(/* @vite-ignore */ fsId)) as Fs;
      const dir = opts.dir ?? 'dist';
      const swPath = `${dir}/sw.js`;
      if (!fs.existsSync(swPath)) return;
      const html = fs.readFileSync(`${dir}/index.html`, 'utf8');
      const refs = new Set<string>();
      for (const m of html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)) refs.add(m[1]);
      for (const ref of [...refs]) {
        if (!ref.endsWith('.css')) continue;
        const css = fs.readFileSync(`${dir}${ref}`, 'utf8');
        for (const m of css.matchAll(/url\((?:"|')?(\/assets\/[^)"']+\.woff2)(?:"|')?\)/g)) refs.add(m[1]);
      }
      const precache = ['/index.html', '/logo.png', '/manifest.webmanifest', ...[...refs].sort()];
      let h = 0x811c9dc5; // FNV-1a
      for (const ch of precache.join('|') + html) { h ^= ch.charCodeAt(0); h = Math.imul(h, 0x01000193) >>> 0; }
      const build = JSON.stringify({ version: h.toString(36), precache });
      const src = fs.readFileSync(swPath, 'utf8');
      const out = src.replace(/const BUILD = \{[^\n]*\};/, `const BUILD = ${build};`);
      if (out === src) this.warn('sw.js: BUILD placeholder not found; the service worker will precache nothing');
      fs.writeFileSync(swPath, out);
    },
  };
}

export default defineConfig({
  plugins: [react(), swPrecache()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: { react: ['react', 'react-dom', 'react-router-dom'], charts: ['uplot'], map: ['leaflet'] },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: API, changeOrigin: true },
      '/healthz': { target: API, changeOrigin: true },
      '/ws': { target: API.replace(/^http/, 'ws'), ws: true, changeOrigin: true },
    },
  },
});
