const SW_VERSION = 'v6';
const STATIC_CACHE = `wallfruits-static-${SW_VERSION}`;
const PAGE_CACHE = `wallfruits-pages-${SW_VERSION}`;
const API_CACHE = `wallfruits-api-${SW_VERSION}`;
const MAX_STATIC_ITEMS = 180;
const MAX_PAGE_ITEMS = 120;
const MAX_API_ITEMS = 80;

const STATIC_PRECACHE = [
  '/',
  '/static/manifest.webmanifest',
  '/static/icon.svg',
  '/static/icon-180.png',
];

function isStaticAsset(request) {
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return false;
  if (url.pathname.startsWith('/static/')) return true;
  return /\.(?:css|js|png|jpg|jpeg|gif|webp|svg|ico|woff2?)$/i.test(url.pathname);
}

function isNavigationRequest(request) {
  return request.mode === 'navigate';
}

function isApiRequest(request) {
  const url = new URL(request.url);
  return url.origin === self.location.origin && url.pathname.startsWith('/api/');
}

function shouldBypassCache(request) {
  if (request.headers && request.headers.has('authorization')) return true;
  const url = new URL(request.url);
  if (request.mode === 'navigate' && url.pathname.startsWith('/store')) return true;
  if (url.searchParams.has('nocache')) return true;
  return false;
}

async function trimCache(cacheName, maxItems) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length <= maxItems) return;
  const extra = keys.length - maxItems;
  for (let i = 0; i < extra; i += 1) {
    await cache.delete(keys[i]);
  }
}

async function putInCache(cacheName, request, response, maxItems) {
  if (!response || !response.ok) return;
  const cache = await caches.open(cacheName);
  await cache.put(request, response.clone());
  await trimCache(cacheName, maxItems);
}

async function networkFirst(request, cacheName, timeoutMs = 2200, maxItems = 120, preloadResponsePromise = null) {
  const timeoutPromise = new Promise((_, reject) => {
    setTimeout(() => reject(new Error('timeout')), timeoutMs);
  });

  try {
    const networkCandidatePromise = (async () => {
      if (preloadResponsePromise) {
        try {
          const preloadResponse = await preloadResponsePromise;
          if (preloadResponse) {
            return preloadResponse;
          }
        } catch (_error) {
          // ignore preload failures and fallback to network fetch
        }
      }

      return fetch(request);
    })();

    const networkResponse = await Promise.race([networkCandidatePromise, timeoutPromise]);
    if (networkResponse && networkResponse.ok) {
      await putInCache(cacheName, request, networkResponse, maxItems);
    }
    return networkResponse;
  } catch (_error) {
    const cached = await caches.match(request);
    if (cached) return cached;

    if (isNavigationRequest(request)) {
      const fallback = await caches.match('/');
      if (fallback) return fallback;
    }

    return new Response('Offline', { status: 503, statusText: 'Offline' });
  }
}

async function staleWhileRevalidate(request, cacheName, maxItems = 120) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(request);

  const networkPromise = fetch(request)
    .then(async (networkResponse) => {
      if (networkResponse && networkResponse.ok) {
        await cache.put(request, networkResponse.clone());
        await trimCache(cacheName, maxItems);
      }
      return networkResponse;
    })
    .catch(() => null);

  if (cached) {
    return cached;
  }

  const network = await networkPromise;
  if (network) return network;

  if (isNavigationRequest(request)) {
    const fallback = await caches.match('/');
    if (fallback) return fallback;
  }

  return new Response('Offline', { status: 503, statusText: 'Offline' });
}

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(STATIC_PRECACHE))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(
      keys.map((key) => {
        if (![STATIC_CACHE, PAGE_CACHE, API_CACHE].includes(key)) {
          return caches.delete(key);
        }
        return Promise.resolve();
      })
    );

    if (self.registration && self.registration.navigationPreload) {
      try {
        await self.registration.navigationPreload.enable();
      } catch (_error) {
        // silently ignore unsupported environments
      }
    }

    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  if (shouldBypassCache(request)) {
    event.respondWith(fetch(request));
    return;
  }

  if (isNavigationRequest(request)) {
    event.respondWith(networkFirst(request, PAGE_CACHE, 2400, MAX_PAGE_ITEMS, event.preloadResponse));
    return;
  }

  if (isApiRequest(request)) {
    event.respondWith(networkFirst(request, API_CACHE, 4200, MAX_API_ITEMS));
    return;
  }

  if (isStaticAsset(request)) {
    event.respondWith(staleWhileRevalidate(request, STATIC_CACHE, MAX_STATIC_ITEMS));
    return;
  }

  event.respondWith(staleWhileRevalidate(request, PAGE_CACHE, MAX_PAGE_ITEMS));
});
