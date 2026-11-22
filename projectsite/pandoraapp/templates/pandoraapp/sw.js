// Pages hold private store data, so nothing is cached; offline navigations get a notice instead.
const OFFLINE = '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><title>Offline</title>'
  + '<body style="font-family:system-ui;background:#2d3250;color:#fff;display:grid;place-items:center;height:100vh;margin:0;text-align:center">'
  + '<div><h1>You are offline</h1><p>Pandora needs a connection. Reconnect and try again.</p>'
  + '<button onclick="location.reload()" style="padding:.6em 1.2em;border:0;border-radius:8px;background:#f9b17a">Retry</button></div>';
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  if (event.request.mode !== 'navigate') return;
  event.respondWith(fetch(event.request).catch(() =>
    new Response(OFFLINE, {headers: {'Content-Type': 'text/html; charset=utf-8'}})));
});
