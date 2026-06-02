const CACHE_NAME = 'ibat-pdv-cache-v5';
const STATIC_ASSETS = [
    '/',
    '/static/pwa/index.html',
    '/static/pwa/styles.css',
    '/static/pwa/app.js',
    '/static/pwa/manifest.json',
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS);
        })
    );
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((name) => name !== CACHE_NAME)
                    .map((name) => caches.delete(name))
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(request).catch(() => {
                return new Response(
                    JSON.stringify({ error: 'Sin conexión al servidor' }),
                    { status: 503, headers: { 'Content-Type': 'application/json' } }
                );
            })
        );
        return;
    }

    event.respondWith(
        caches.match(request).then((cached) => {
            return cached || fetch(request).then((response) => {
                return caches.open(CACHE_NAME).then((cache) => {
                    cache.put(request, response.clone());
                    return response;
                });
            });
        })
    );
});
