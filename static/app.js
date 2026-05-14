// 위험성평가 클라이언트 스크립트
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

  // 온라인일 때 오프라인 폼 HTML을 localStorage에 저장
  function saveOfflineForm() {
    if (!navigator.onLine) return;
    fetch("/static/offline_form.html")
      .then(res => res.text())
      .then(html => {
        localStorage.setItem("offline_form_html", html);
        localStorage.setItem("offline_form_saved_at", new Date().toISOString());
      })
      .catch(() => {});
  }

  // 대시보드에서 자동 저장
  if (document.querySelector(".bottom-nav")) {
    setTimeout(saveOfflineForm, 1500);
  }

  // 폼 자동 임시 저장 + 오프라인 큐
  const form = document.getElementById("assessment-form");
  if (form) {
    const DRAFT_KEY = "ra_draft";
    const QUEUE_KEY = "pending_assessments";

    // 임시저장 복원
    try {
      const saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null");
      if (saved && Object.keys(saved).length > 0) {
        if (confirm("저장된 임시 작성 내용이 있습니다. 불러올까요?")) {
          for (const [k, v] of Object.entries(saved)) {
            const els = form.querySelectorAll(`[name="${k}"]`);
            if (!els.length) continue;
            if (els[0].type === "radio") {
              els.forEach(e => { if (e.value === v) e.checked = true; });
            } else if (els[0].type === "checkbox") {
              const vals = Array.isArray(v) ? v : [v];
              els.forEach(e => { e.checked = vals.includes(e.value); });
            } else {
              els[0].value = v;
            }
          }
        }
      }
    } catch (e) {}

    // 자동 저장
    form.addEventListener("input", () => {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(formToObject(form)));
    });
    form.addEventListener("change", () => {
      localStorage.setItem(DRAFT_KEY, JSON.stringify(formToObject(form)));
    });

    // 제출 처리
    form.addEventListener("submit", (e) => {
      if (!navigator.onLine) {
        e.preventDefault();
        const obj = formToObject(form);
        const queue = JSON.parse(localStorage.getItem(QUEUE_KEY) || "[]");
        queue.push({ id: Date.now(), data: obj, savedAt: new Date().toISOString() });
        localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
        localStorage.removeItem(DRAFT_KEY);
        alert("오프라인 상태입니다. 인터넷 연결 시 자동으로 제출됩니다.");
        history.back();
      } else {
        localStorage.removeItem(DRAFT_KEY);
      }
    });
  }

  // 온라인 복구 시 자동 제출
  async function trySyncQueue() {
    const queue = JSON.parse(localStorage.getItem("pending_assessments") || "[]");
    if (!queue.length) return;
    let successCount = 0;
    const remaining = [];
    for (const item of queue) {
      try {
        const formData = new FormData();
        for (const [k, v] of Object.entries(item.data)) {
          const vals = Array.isArray(v) ? v : [v];
          vals.forEach(val => formData.append(k, val));
        }
        const res = await fetch("/assessment/new", {
          method: "POST",
          body: formData,
          credentials: "include"
        });
        if (res.ok || res.redirected) {
          successCount++;
        } else {
          remaining.push(item);
        }
      } catch (e) {
        remaining.push(item);
      }
    }
    localStorage.setItem("pending_assessments", JSON.stringify(remaining));
    if (successCount > 0) {
      alert(`📤 오프라인 저장본 ${successCount}건이 자동 제출되었습니다!`);
      location.reload();
    }
  }

  if (navigator.onLine) trySyncQueue();

  function formToObject(form) {
    const obj = {};
    const fd = new FormData(form);
    for (const [k, v] of fd.entries()) {
      if (obj[k] !== undefined) {
        if (!Array.isArray(obj[k])) obj[k] = [obj[k]];
        obj[k].push(v);
      } else {
        obj[k] = v;
      }
    }
    return obj;
  }
})();
