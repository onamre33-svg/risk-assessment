// 위험성평가 PWA 서비스워커
// - 정적 파일 캐싱
// - 오프라인시 캐시 응답
// - 폼 제출은 백그라운드 동기화 대신, 클라이언트에서 localStorage 기반으로 재제출

const CACHE = "ra-v1";
const ASSETS = [
  "/",
  "/login",
  "/static/style.css",
  "/static/app.js",
  "/static/manifest.json",
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
  // POST 등 비-GET은 캐싱하지 않고 네트워크로
  if (req.method !== "GET") return;

  e.respondWith(
    fetch(req)
      .then((res) => {
        // 동일 출처 GET만 캐시에 갱신
        const url = new URL(req.url);
        if (url.origin === location.origin) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then((r) => r || caches.match("/login")))
  );
});
