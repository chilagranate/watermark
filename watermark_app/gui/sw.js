self.addEventListener('install', e => {
  e.waitUntil(
    caches.open('wm-v1').then(cache => cache.addAll([
      '/', '/static/style.css', '/static/app.js',
    ]))
  );
});
self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request))
  );
});
