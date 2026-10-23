/* Service worker: offline app shell, cached ward shapes, and flood-alert notifications. */
const VERSION = 'v1';
const SHELL = `flood-shell-${VERSION}`;
const DATA = `flood-data-${VERSION}`;
const SHELL_URLS = ['/', '/manifest.webmanifest', '/favicon.svg', '/icons/icon-192.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL).then((cache) => cache.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== SHELL && k !== DATA).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const isWardShapes = (url) => url.pathname === '/api/v1/wards/lite' || url.pathname === '/api/v1/wards';
const isActiveAlerts = (url) => url.pathname === '/api/v1/alerts/active';

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch (error) {
    const cached = await cache.match(request);
    if (cached) return cached;
    throw error;
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(DATA);
  const cached = await cache.match(request);
  const refresh = fetch(request).then((response) => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  });
  return cached || refresh;
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    // fresh page when online, cached app when offline
    event.respondWith(fetch(request).catch(() => caches.match('/')));
  } else if (url.pathname.startsWith('/assets/')) {
    // hashed file names never change: cache forever
    event.respondWith(caches.match(request).then((hit) => hit || networkFirst(request, SHELL)));
  } else if (isWardShapes(url)) {
    event.respondWith(staleWhileRevalidate(request));
  } else if (isActiveAlerts(url)) {
    // last known alerts are still useful offline
    event.respondWith(networkFirst(request, DATA));
  }
});

/** Only open pages on this site for an alert; never a URL taken from the payload. */
function alertUrl(id) {
  return typeof id === 'string' && /^[\w-]{1,80}$/.test(id) ? `/?alert=${encodeURIComponent(id)}` : '/';
}

function showAlert(payload) {
  const title = String(payload.title || 'Flood alert').slice(0, 80);
  const body = String(payload.body || '').slice(0, 300);
  return self.registration.showNotification(title, {
    body,
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    tag: `ward-${Number(payload.ward_id) || 0}`,
    renotify: true,
    requireInteraction: payload.level === 'warning',
    vibrate: [300, 100, 300, 100, 600],
    data: { url: alertUrl(payload.id) },
  });
}

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { body: event.data ? event.data.text() : '' };
  }
  event.waitUntil(showAlert(payload));
});

// The page asks for a notification when the alert preview delivers one.
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SHOW_ALERT') event.waitUntil(showAlert(event.data.payload || {}));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    })
  );
});
