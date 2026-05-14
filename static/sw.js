// 위험성평가 PWA 서비스워커
const CACHE = "ra-v2";
const ASSETS = [
  "/",
  "/login",
  "/assessment/new",
  "/static/style.css",
  "/static/app.js",
  "/static/manifest.json",
  "/static/icon-192.png",
  "/static/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) =>
      c.addAll(ASSETS).catch(() => {})
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // assessment/new, dashboard 페이지는 캐시 우선 (오프라인 지원)
  const offlinePages = ["/assessment/new", "/", "/login"];
  const isOfflinePage = offlinePages.some(p => url.pathname === p || url.pathname.startsWith(p));

  if (isOfflinePage) {
    e.respondWith(
      caches.match(req).then((cached) => {
        // 네트워크 먼저 시도, 실패 시 캐시
        return fetch(req)
          .then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(CACHE).then((c) => c.put(req, copy));
            }
            return res;
          })
          .catch(() => cached || caches.match("/login"));
      })
    );
    return;
  }

  // 정적 파일은 캐시 우선
  if (url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(req).then((cached) => {
        return cached || fetch(req).then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
          return res;
        });
      })
    );
    return;
  }

  // 나머지는 네트워크 우선, 실패 시 캐시
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (url.origin === location.origin && res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then((r) => r || caches.match("/login")))
  );
});
