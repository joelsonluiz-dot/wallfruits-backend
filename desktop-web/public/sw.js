const CACHE_VERSION = 'wallfruits-pwa-v1';
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;
const OFFLINE_URL = '/offline.html';

const PRECACHE_URLS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/offline.html',
  '/pwa-icon.svg',
  '/pwa-icon-maskable.svg',
  '/pwa-icon-192.png',
  '/pwa-icon-512.png',
  '/apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.map((key) => (key.startsWith('wallfruits-pwa-') ? Promise.resolve() : caches.delete(key)))
    );
    await self.clients.claim();
  })());
});

async function cacheFirst(request) {
  const cache = await caches.open(RUNTIME_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response && response.ok) {
    cache.put(request, response.clone());
  }
  return response;
}

// Simple cache with max entries helper
async function putInCacheWithLimit(cacheName, request, response, maxEntries = 60) {
  const cache = await caches.open(cacheName);
  await cache.put(request, response.clone());
  const keys = await cache.keys();
  if (keys.length > maxEntries) {
    // delete oldest
    await cache.delete(keys[0]);
  }
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  if (request.mode === 'navigate') {
    event.respondWith((async () => {
      try {
        const networkResponse = await fetch(request);
        return networkResponse;
      } catch {
        const cached = await caches.match('/index.html');
        if (cached) return cached;
        const offline = await caches.match(OFFLINE_URL);
        return offline || new Response('Offline', { status: 503, statusText: 'Offline' });
      }
    })());
    return;
  }

  if (url.origin === self.location.origin && (request.destination === 'script' || request.destination === 'style' || request.destination === 'image' || request.destination === 'font')) {
    // images: limit cache size
    if (request.destination === 'image') {
      event.respondWith((async () => {
        const cached = await caches.match(request);
        if (cached) return cached;
        try {
          const resp = await fetch(request);
          if (resp && resp.ok) await putInCacheWithLimit(RUNTIME_CACHE, request, resp, 100);
          return resp;
        } catch (e) {
          return cached || Response.error();
        }
      })());
      return;
    }

    event.respondWith(cacheFirst(request));
  }

  // Stale-while-revalidate for API JSON calls
  if (url.pathname.startsWith('/api/')) {
    event.respondWith((async () => {
      const cache = await caches.open(RUNTIME_CACHE + '-api');
      const cached = await cache.match(request);
      const networkFetch = fetch(request).then((r) => {
        if (r && r.ok) cache.put(request, r.clone());
        return r;
      }).catch(() => null);

      return (await networkFetch) || cached || new Response(null, { status: 503 });
    })());
  }
});