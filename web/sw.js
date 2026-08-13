// Service worker — caches the interface, and nothing else.
//
// The one rule here: **/api/ is never cached.** A journal that shows yesterday's
// answers because a stale response was served would be worse than a journal
// that plainly refuses to load. Everything under /api/ goes straight to the
// network, every time, and a failure surfaces as a failure.
//
// What is cached is the shell — the HTML, CSS, JS and icons. Network-first, so
// an updated app is picked up the moment the server is reachable; the cache is
// only there so the window opens at all when it is not.
//
// Note this file only ever runs over HTTPS or on localhost. Opening the desktop
// app from a phone on the same network uses a plain http:// LAN address, which
// browsers refuse to register a service worker for — see registerServiceWorker()
// in app.js. That is a limitation of the current desktop-server setup, not of
// this file, and it goes away when the app is served as a real PWA.

const CACHE = "journal-shell-v1";

const SHELL = [
  "/",
  "/static/styles.css",
  "/static/app.js",
  "/static/icon.svg",
  "/static/icon-180.png",
  "/static/icon-512.png",
  "/manifest.webmanifest",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      // addAll fails the whole install if any single entry 404s, which would
      // leave no worker at all. Each file is added on its own instead.
      .then((cache) => Promise.all(SHELL.map((url) => cache.add(url).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // never cached, never guessed at

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(async () => {
        const hit = await caches.match(request);
        if (hit) return hit;
        if (request.mode === "navigate") {
          const shell = await caches.match("/");
          if (shell) return shell;
        }
        return new Response("離線中，而且這一份還沒有存下來。", {
          status: 503,
          headers: { "Content-Type": "text/plain; charset=utf-8" },
        });
      })
  );
});
