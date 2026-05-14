// 위험성평가 클라이언트 스크립트
// - 서비스워커 등록
// - 오프라인 배너
// - 폼 자동 임시저장 (localStorage)
// - 네트워크 복구 시 자동 재제출

(function () {
  // 서비스워커 등록
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  }

  // 오프라인 배너
  const banner = document.createElement("div");
  banner.className = "offline-banner";
  banner.textContent = "📡 오프라인 상태입니다. 작성 내용은 자동으로 임시 저장되며, 인터넷 연결 시 자동 제출됩니다.";
  document.body.appendChild(banner);
  function updateOnline() {
    banner.classList.toggle("show", !navigator.onLine);
  }
  window.addEventListener("online", () => { updateOnline(); trySyncQueue(); });
  window.addEventListener("offline", updateOnline);
  updateOnline();

  // 폼 자동 임시 저장 + 오프라인 큐
  const form = document.getElementById("raForm");
  if (form) {
    const DRAFT_KEY = "ra_draft";
    const QUEUE_KEY = "ra_queue";

    // 복원
    try {
      const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
      if (saved && confirm("저장된 임시 작성 내용이 있습니다. 불러올까요?")) {
        for (const [k, v] of Object.entries(saved)) {
          const el = form.elements.namedItem(k);
          if (!el) continue;
          if (el.type === "checkbox" || el.type === "radio") {
            form.querySelectorAll(`[name="${k}"]`).forEach((e) => {
              if (e.value === v || (Array.isArray(v) && v.includes(e.value))) e.checked = true;
            });
          } else {
            el.value = v;
          }
        }
      }
    } catch (e) {}

    // 자동 저장 (변경 시)
    form.addEventListener("input", () => {
      const data = formToObject(form);
      localStorage.setItem(DRAFT_KEY, JSON.stringify(data));
    });

    // 제출
    form.addEventListener("submit", (e) => {
      if (!navigator.onLine) {
        e.preventDefault();
        const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
        queue.push(formToObject(form));
        localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
        localStorage.removeItem(DRAFT_KEY);
        alert("오프라인 상태이므로 임시 저장되었습니다. 인터넷 연결 시 자동 제출됩니다.");
        window.location.href = "/dashboard";
      } else {
        localStorage.removeItem(DRAFT_KEY);
      }
    });
  }

  async function trySyncQueue() {
    const queue = JSON.parse(localStorage.getItem("ra_queue") || "[]");
    if (!queue.length) return;
    try {
      const res = await fetch("/api/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: queue }),
      });
      const body = await res.json();
      if (body.ok) {
        localStorage.removeItem("ra_queue");
        if (body.saved_ids && body.saved_ids.length) {
          alert(`오프라인 저장본 ${body.saved_ids.length}건이 자동 제출되었습니다.`);
        }
      }
    } catch (e) {
      // 다음에 다시 시도
    }
  }
  // 페이지 로드 시 한 번 시도
  if (navigator.onLine) trySyncQueue();

  function formToObject(form) {
    const obj = {};
    const fd = new FormData(form);
    for (const [k, v] of fd.entries()) {
      if (obj[k] !== undefined) {
        if (!Array.isArray(obj[k])) obj[k] = [obj[k]];
        obj[k].push(v);
      } else obj[k] = v;
    }
    return obj;
  }
})();
