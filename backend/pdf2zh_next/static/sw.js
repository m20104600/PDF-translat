const CACHE_NAME = 'pdf-trans-v1';
const ASSETS = [
    '/static/upload.html',
    '/static/login.html',
    '/static/dashboard.html',
    '/static/manifest.json',
    '/static/css/style.css'
];

self.addEventListener('install', (e) => {
    e.waitUntil(
        caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
    );
});

self.addEventListener('fetch', (e) => {
    // Strategy: Network First, fallback to cache
    e.respondWith(
        fetch(e.request)
            .catch(() => caches.match(e.request))
    );
});
