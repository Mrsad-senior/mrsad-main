/* Mirsad approver service worker.
 * Generated at build time from web/src/approver/sw.template.js: the precache list and
 * version are injected by the `mirsad-approver-sw` Vite plugin (vite.config.ts).
 *
 * Strategy: precache the app shell; network-first for navigations and for the approval
 * API (so the last known queue is visible offline); cache-first for hashed /assets/*;
 * the SSE stream and every non-GET request bypass the worker entirely.
 */
const VERSION = 'e6561af85e9b';
const SHELL_CACHE = `mirsad-shell-${VERSION}`;
const API_CACHE = 'mirsad-api-v1';
const PREFS_CACHE = 'mirsad-prefs-v1';
const PRECACHE = ["/approve","/assets/manifest.webmanifest","/assets/icons/icon-192.png","/assets/favicon.svg","/assets/approve-DfdRfI8P.css","/assets/approve-HNF6B36P.js","/assets/modulepreload-polyfill-B5Qt9EMX.js","/assets/react-DqJZAsTa.js","/assets/shared-DNBHfjoW.js","/assets/shared-kDDY3Qbn.css"];
// Only approval data is kept for offline viewing; it is cleared on sign-out.
const CACHEABLE_API = [/^\/api\/approvals(\/|$|\?)/, /^\/api\/auth\/me$/];

self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      // One missing file must not prevent installation.
      await Promise.allSettled(PRECACHE.map((url) => cache.add(new Request(url, { cache: 'reload' }))));
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k.startsWith('mirsad-shell-') && k !== SHELL_CACHE).map((k) => caches.delete(k)));
      await self.clients.claim();
    })(),
  );
});

async function networkFirst(request, cacheName, fallbackUrl) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok && response.type === 'basic') await cache.put(fallbackUrl || request, response.clone());
    return response;
  } catch (err) {
    const cached = (await cache.match(fallbackUrl || request)) || (fallbackUrl ? await caches.match(fallbackUrl) : undefined);
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response.ok) {
    const cache = await caches.open(SHELL_CACHE);
    await cache.put(request, response.clone());
  }
  return response;
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === '/api/stream') return;

  if (url.pathname.startsWith('/api/')) {
    if (CACHEABLE_API.some((re) => re.test(url.pathname + url.search))) {
      event.respondWith(networkFirst(request, API_CACHE));
    }
    return;
  }
  if (request.mode === 'navigate' && url.pathname.startsWith('/approve')) {
    event.respondWith(networkFirst(request, SHELL_CACHE, '/approve'));
    return;
  }
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith(cacheFirst(request));
  }
});

// ------------------------------------------------------------------ preferences from the page

async function readLang() {
  try {
    const cache = await caches.open(PREFS_CACHE);
    const res = await cache.match('/__mirsad_prefs');
    const prefs = res ? await res.json() : {};
    return prefs.lang === 'ar' ? 'ar' : 'en';
  } catch {
    return 'en';
  }
}

self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type === 'clear-api-cache') {
    event.waitUntil(caches.delete(API_CACHE));
  } else if (data.type === 'set-lang') {
    event.waitUntil(
      caches.open(PREFS_CACHE).then((cache) =>
        cache.put('/__mirsad_prefs', new Response(JSON.stringify({ lang: data.lang }), { headers: { 'Content-Type': 'application/json' } })),
      ),
    );
  }
});

// ------------------------------------------------------------------ Web Push

const TEXT = {
  en: { title: (tool) => `Approval needed: ${tool}`, generic: 'Mirsad: an agent action needs your decision' },
  ar: { title: (tool) => `مطلوب موافقتك: ${tool}`, generic: 'مرصاد: إجراء لوكيل ذكي بانتظار قرارك' },
};

self.addEventListener('push', (event) => {
  event.waitUntil(
    (async () => {
      let data = {};
      try {
        data = event.data ? event.data.json() : {};
      } catch {
        data = { body: event.data ? event.data.text() : '' };
      }
      const lang = await readLang();
      // Server payload (approvals/service.py): {type, id, tool, risk, title, title_ar, body, body_ar, url, expires_at}.
      const record = data.record || data.approval || data;
      const id = data.approval_id || record.id;
      const tool = typeof record.tool === 'string' ? record.tool : '';
      const serverTitle = lang === 'ar' ? data.title_ar || data.title : data.title || data.title_ar;
      const title = tool ? TEXT[lang].title(tool) : serverTitle || TEXT[lang].generic;
      const body =
        (lang === 'ar'
          ? data.body_ar || record.summary_ar || data.body || record.summary_en
          : data.body || record.summary_en || data.body_ar || record.summary_ar) || '';
      await self.registration.showNotification(title, {
        body,
        tag: id ? `approval-${id}` : 'mirsad',
        icon: '/assets/icons/icon-192.png',
        badge: '/assets/icons/badge-96.png',
        lang,
        dir: lang === 'ar' ? 'rtl' : 'ltr',
        requireInteraction: true,
        data: { url: id ? `/approve#/a/${encodeURIComponent(id)}` : '/approve' },
      });
    })(),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || '/approve', self.location.origin).href;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      for (const client of windows) {
        if (new URL(client.url).pathname.startsWith('/approve')) {
          await client.focus();
          client.postMessage({ type: 'open', url: target });
          return;
        }
      }
      await self.clients.openWindow(target);
    })(),
  );
});
