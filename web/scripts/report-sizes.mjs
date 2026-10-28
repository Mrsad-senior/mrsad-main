#!/usr/bin/env node
/**
 * Bundle size report for the built web app (run by `npm run build` after `vite build`).
 *
 * Prints every emitted JS/CSS file with raw and gzip sizes, then the *initial* payload of each
 * entry page (the scripts, module preloads and stylesheets referenced by index.html and
 * approve.html). Lazy-loaded dashboard pages are listed but not counted as initial.
 * Budgets are advisory: exceeding one prints a warning, it never fails the build.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

const here = fileURLToPath(new URL('.', import.meta.url));
const OUT = resolve(here, '../../src/mirsad/static');
// Advisory, set just above the current size so growth is noticed (React alone is ~45 kB gzip).
const BUDGET_GZIP_KB = { 'index.html': 120, 'approve.html': 105 };

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

const kb = (n) => `${(n / 1024).toFixed(1)} kB`;
const sizeOf = (path) => {
  const data = readFileSync(path);
  return { raw: data.length, gzip: gzipSync(data, { level: 9 }).length };
};

let files;
try {
  files = walk(OUT).filter((f) => /\.(js|css|html|webmanifest|json)$/.test(f));
} catch {
  console.error(`report-sizes: build output not found at ${OUT}`);
  process.exit(1);
}

const rows = files
  .map((f) => ({ path: relative(OUT, f).split('\\').join('/'), ...sizeOf(f) }))
  .sort((a, b) => b.gzip - a.gzip);

const width = Math.max(...rows.map((r) => r.path.length), 10);
console.log(`\nMirsad web build -> ${OUT}\n`);
console.log(`${'file'.padEnd(width)}  ${'raw'.padStart(10)}  ${'gzip'.padStart(10)}`);
for (const r of rows) console.log(`${r.path.padEnd(width)}  ${kb(r.raw).padStart(10)}  ${kb(r.gzip).padStart(10)}`);

let warned = false;
console.log('\nInitial payload per entry (HTML + referenced JS/CSS, excluding lazy pages):');
for (const entry of ['index.html', 'approve.html']) {
  const htmlPath = join(OUT, entry);
  let html;
  try {
    html = readFileSync(htmlPath, 'utf8');
  } catch {
    console.log(`  ${entry}: missing`);
    continue;
  }
  const refs = new Set([entry]);
  for (const m of html.matchAll(/(?:src|href)="\/([^"]+\.(?:js|css))"/g)) refs.add(m[1]);
  let raw = 0;
  let gzip = 0;
  for (const ref of refs) {
    const s = sizeOf(join(OUT, ref));
    raw += s.raw;
    gzip += s.gzip;
  }
  const budget = BUDGET_GZIP_KB[entry];
  const over = gzip / 1024 > budget;
  warned ||= over;
  console.log(`  ${entry.padEnd(13)} ${String(refs.size).padStart(2)} files  ${kb(raw).padStart(10)} raw  ${kb(gzip).padStart(10)} gzip  (budget ${budget} kB gzip${over ? ', EXCEEDED' : ''})`);
}

const total = rows.reduce((acc, r) => ({ raw: acc.raw + r.raw, gzip: acc.gzip + r.gzip }), { raw: 0, gzip: 0 });
console.log(`\nAll text assets: ${kb(total.raw)} raw, ${kb(total.gzip)} gzip`);
if (warned) console.warn('report-sizes: an initial payload is over its advisory budget.');
