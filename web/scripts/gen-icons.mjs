// Generates the PWA icons (valid RGBA PNGs) from the Mirsad logo geometry using only
// Node built-ins. The shapes mirror src/shared/components/Logo.tsx (64x64 design grid):
// a watchtower roof (chevron) above an almond eye with iris and pupil.
//
//   node scripts/gen-icons.mjs
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deflateSync } from 'node:zlib';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(here, '../public/assets/icons');

const NAVY = [11, 31, 58, 255];
const TEAL = [45, 212, 191, 255];
const WHITE = [255, 255, 255, 255];

// ---------------------------------------------------------------- geometry (64-unit grid)
function inRoundedRect(x, y, size, radius) {
  const r = radius;
  const cx = Math.min(Math.max(x, r), size - r);
  const cy = Math.min(Math.max(y, r), size - r);
  return x >= 0 && y >= 0 && x <= size && y <= size && (x - cx) ** 2 + (y - cy) ** 2 <= r * r;
}

function distToSegment(px, py, ax, ay, bx, by) {
  const dx = bx - ax;
  const dy = by - ay;
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (ax + t * dx), py - (ay + t * dy));
}

const inRoof = (x, y) =>
  distToSegment(x, y, 14, 29, 32, 15) <= 2.6 || distToSegment(x, y, 32, 15, 50, 29) <= 2.6;

function inEye(x, y) {
  if (x < 12 || x > 52) return false;
  const t = (x - 12) / 40; // the Bezier x(t) is linear because the control point is centred
  const half = 36 * t * (1 - t);
  return y >= 42 - half && y <= 42 + half;
}

const inCircle = (x, y, cx, cy, r) => (x - cx) ** 2 + (y - cy) ** 2 <= r * r;

/** Colour of the logo at design-grid point (x, y), or null for transparent. */
function logoColour(x, y, { background, mono }) {
  const fg = mono ? WHITE : TEAL;
  if (inCircle(x, y, 32, 42, 3)) return fg;
  if (inCircle(x, y, 32, 42, 7.5)) return mono ? null : NAVY;
  if (inEye(x, y) || inRoof(x, y)) return fg;
  return background;
}

// ---------------------------------------------------------------- rasteriser (4x4 supersampling)
function render(size, { maskable = false, rounded = true, mono = false } = {}) {
  const px = new Uint8Array(size * size * 4);
  const scale = maskable ? 0.64 : 1; // maskable icons keep content inside the 80% safe zone
  const offset = (64 - 64 * scale) / 2;
  const S = 4;
  for (let j = 0; j < size; j++) {
    for (let i = 0; i < size; i++) {
      let r = 0, g = 0, b = 0, a = 0;
      for (let sj = 0; sj < S; sj++) {
        for (let si = 0; si < S; si++) {
          const gx = ((i + (si + 0.5) / S) / size) * 64;
          const gy = ((j + (sj + 0.5) / S) / size) * 64;
          let background = null;
          if (!mono) {
            background = rounded && !maskable ? (inRoundedRect(gx, gy, 64, 14) ? NAVY : null) : NAVY;
          }
          let colour = background;
          if (!mono && background === null) colour = null;
          else {
            const lx = (gx - offset) / scale;
            const ly = (gy - offset) / scale;
            colour = logoColour(lx, ly, { background, mono });
          }
          if (colour) {
            const alpha = colour[3] / 255;
            r += colour[0] * alpha; g += colour[1] * alpha; b += colour[2] * alpha; a += alpha;
          }
        }
      }
      const k = (j * size + i) * 4;
      const n = S * S;
      px[k] = a ? Math.round(r / a) : 0;
      px[k + 1] = a ? Math.round(g / a) : 0;
      px[k + 2] = a ? Math.round(b / a) : 0;
      px[k + 3] = Math.round((a / n) * 255);
    }
  }
  return px;
}

// ---------------------------------------------------------------- PNG encoder
const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (const byte of buf) c = CRC_TABLE[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, 'ascii'), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

export function encodePng(size, rgba) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // colour type RGBA
  ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  const raw = Buffer.alloc(size * (size * 4 + 1));
  for (let y = 0; y < size; y++) {
    raw[y * (size * 4 + 1)] = 0; // filter: none
    Buffer.from(rgba.buffer, y * size * 4, size * 4).copy(raw, y * (size * 4 + 1) + 1);
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk('IHDR', ihdr),
    chunk('IDAT', deflateSync(raw, { level: 9 })),
    chunk('IEND', Buffer.alloc(0)),
  ]);
}

const targets = [
  ['icon-192.png', 192, { rounded: true }],
  ['icon-512.png', 512, { rounded: true }],
  ['icon-maskable-512.png', 512, { maskable: true }],
  ['apple-touch-icon.png', 180, { rounded: false }],
  ['badge-96.png', 96, { mono: true }],
];

mkdirSync(outDir, { recursive: true });
for (const [name, size, opts] of targets) {
  const file = resolve(outDir, name);
  writeFileSync(file, encodePng(size, render(size, opts)));
  console.log(`wrote ${name} (${size}x${size})`);
}
