import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import type { Plugin } from 'vite';
import { defineConfig } from 'vitest/config';

const root = fileURLToPath(new URL('.', import.meta.url));
const API_TARGET = process.env.MIRSAD_API ?? 'http://127.0.0.1:8700';

/**
 * Emits `approve-sw.js` at the output root with a precache list of exactly the
 * files the approver entry needs (hashed names are only known after bundling).
 * The worker must live at the site root so its scope can cover `/approve`.
 */
function approverServiceWorker(): Plugin {
  return {
    name: 'mirsad-approver-sw',
    apply: 'build',
    generateBundle(_options, bundle) {
      const files = new Set<string>();
      const visit = (fileName: string): void => {
        const item = bundle[fileName];
        if (!item || files.has(`/${fileName}`)) return;
        files.add(`/${fileName}`);
        if (item.type === 'chunk') {
          item.imports.forEach(visit);
          item.viteMetadata?.importedCss.forEach((css) => files.add(`/${css}`));
          item.viteMetadata?.importedAssets.forEach((asset) => files.add(`/${asset}`));
        }
      };
      for (const item of Object.values(bundle)) {
        if (item.type === 'chunk' && item.isEntry && item.name === 'approve') visit(item.fileName);
      }
      const shell = [
        '/approve',
        '/assets/manifest.webmanifest',
        '/assets/icons/icon-192.png',
        '/assets/favicon.svg',
        ...[...files].sort(),
      ];
      const version = createHash('sha256').update(shell.join('\n')).digest('hex').slice(0, 12);
      const template = readFileSync(resolve(root, 'src/approver/sw.template.js'), 'utf8');
      const source = template
        .replace('self.__MIRSAD_PRECACHE__', JSON.stringify(shell))
        .replace('__MIRSAD_SW_VERSION__', version);
      this.emitFile({ type: 'asset', fileName: 'approve-sw.js', source });
    },
  };
}

/** Dev only: serve the PWA at `/approve` like the FastAPI app does in production. */
function devApproveRoute(): Plugin {
  return {
    name: 'mirsad-dev-approve-route',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use((req, _res, next) => {
        if (req.url && /^\/approve\/?(\?.*)?$/.test(req.url)) {
          const query = req.url.includes('?') ? req.url.slice(req.url.indexOf('?')) : '';
          req.url = `/approve.html${query}`;
        }
        next();
      });
    },
  };
}

export default defineConfig({
  root,
  base: '/',
  plugins: [react(), approverServiceWorker(), devApproveRoute()],
  build: {
    // `npm run build` writes ./dist, the only folder deployed to Cloudflare (wrangler.jsonc).
    // `npm run build:gateway` overrides this with ../src/mirsad/static, which FastAPI serves.
    outDir: resolve(root, 'dist'),
    emptyOutDir: true,
    assetsDir: 'assets',
    // CSP is `self` only (img-src excludes data:), so never inline assets as data: URIs.
    assetsInlineLimit: 0,
    target: 'es2020',
    sourcemap: false,
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      input: {
        index: resolve(root, 'index.html'),
        approve: resolve(root, 'approve.html'),
      },
      output: {
        // Stable, readable chunk names: the approver loads react + shared only, never charts.
        manualChunks(id) {
          if (/node_modules\/(react|react-dom|scheduler)\//.test(id)) return 'react';
          if (/node_modules\/(recharts|d3-|victory-vendor|@reduxjs|react-redux|redux|immer|reselect|es-toolkit|decimal\.js-light|eventemitter3)/.test(id)) return 'charts';
          if (id.includes('/src/shared/')) return 'shared';
          return undefined;
        },
      },
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': { target: API_TARGET, changeOrigin: false },
      '/v1': { target: API_TARGET, changeOrigin: false },
      '/healthz': { target: API_TARGET, changeOrigin: false },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['tests/**/*.test.{ts,tsx}'],
    setupFiles: ['tests/setup.ts'],
    css: false,
    restoreMocks: true,
  },
});
