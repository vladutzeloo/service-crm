// service-crm — minimal "PWA-light" service worker.
//
// Caches the app shell + static assets so the topbar/sidebar/CSS still
// paint when the network's flaky. v1.0 deliberately does NOT cache
// state-changing writes — technicians need an online connection to log
// a visit. Offline write queueing is a v1.2 feature.
//
// Versioned cache key tied to ``VERSION`` (passed via service-worker.js
// query string at registration time). When the version changes the new
// SW takes over via skip-waiting + clients.claim + page reload.

const VERSION = new URL(self.location.href).searchParams.get("v") || "0.0.0";
const CACHE_NAME = "scrm-shell-" + VERSION;

const SHELL_ASSETS = [
  "/",
  "/static/css/style.css",
  "/static/js/app.js",
  "/static/manifest.webmanifest",
  "/static/icons/icon.svg",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(SHELL_ASSETS).catch(function () {
        // Best-effort precache — a missing asset shouldn't block install.
      });
    })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches
      .keys()
      .then(function (keys) {
        return Promise.all(
          keys
            .filter(function (k) { return k !== CACHE_NAME; })
            .map(function (k) { return caches.delete(k); })
        );
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener("message", function (event) {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});

self.addEventListener("fetch", function (event) {
  var req = event.request;

  // Never cache writes. Pass them straight through; technicians get a
  // network error if they're offline, which surfaces the state honestly.
  if (req.method !== "GET") return;

  // Same-origin static assets: cache-first.
  var url = new URL(req.url);
  if (url.origin === self.location.origin && url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(req).then(function (cached) {
        return (
          cached ||
          fetch(req).then(function (resp) {
            if (resp && resp.ok) {
              var clone = resp.clone();
              caches.open(CACHE_NAME).then(function (c) { c.put(req, clone); });
            }
            return resp;
          })
        );
      })
    );
    return;
  }

  // Navigations: network-first, fall back to the cached shell.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(function () {
        return caches.match("/").then(function (cached) {
          return cached || new Response("Offline", { status: 503 });
        });
      })
    );
  }
});
