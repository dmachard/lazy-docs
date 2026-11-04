const CACHE_NAME = 'lazydocs-v1.1';
const STATIC_ASSETS = [
    '/',
    '/style.css?v=15.0',
    '/app.js?v=16.0',
    '/manifest.json',
    '/icon.svg',
    '/icon-192.png',
    '/icon-512.png'
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(STATIC_ASSETS).catch(err => {
                console.warn('Pre-cache partial failure:', err);
            });
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Bypass cache for API endpoints and raw document files
    if (url.pathname.startsWith('/api/') || url.pathname.includes('/file')) {
        return;
    }

    // Bypass cache for Web Share Target POST submissions
    if (url.pathname === '/share-target' && event.request.method === 'POST') {
        return;
    }

    event.respondWith(
        fetch(event.request).catch(() => caches.match(event.request))
    );
});
