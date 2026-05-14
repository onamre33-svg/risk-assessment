// 위험성평가 PWA 서비스워커 v5
const CACHE = "ra-v5";
const OFFLINE_FORM = "/static/offline_form.html";

self.addEventListener("install", (e) => {
  // addAll 대신 개별 fetch로 캐시
  e.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      const urls = ["/", "/login", "/static/offline_form.html", "/static/style.css", "/static/app.js"];
      for (const url of urls) {
        try {
          const res = await fetch(url);
          if (res.ok) await cache.put(url, res);
        } catch(e) {}
      }
    })
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

  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then((r) => r || caches.match("/login")))
  );
});
