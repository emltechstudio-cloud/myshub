const CACHE_NAME='myshub-v3';
const urlsToCache=['/app.html','/discover.html','/shop.html','/index.html','/admin.html','/manifest.json'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE_NAME).then(c=>c.addAll(urlsToCache)));self.skipWaiting()});
self.addEventListener('fetch',e=>{e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)))});
self.addEventListener('push',e=>{const d=e.data.json();e.waitUntil(self.registration.showNotification(d.title,{body:d.body,icon:'https://cdn-icons-png.flaticon.com/512/10828/10828179.png',badge:'https://cdn-icons-png.flaticon.com/512/10828/10828179.png',data:d.url}))});
self.addEventListener('notificationclick',e=>{e.notification.close();e.waitUntil(clients.openWindow(e.notification.data||'/'))});