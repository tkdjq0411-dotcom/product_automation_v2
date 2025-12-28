console.log("✅ common.js LOADED");

/* =========================
   Supabase 초기화 (단 1번)
========================= */
let supabaseClient = null;

async function initSupabase() {
  if (supabaseClient) return supabaseClient;

  const res = await fetch("/api/public-config");
  const cfg = await res.json();

  supabaseClient = window.supabase.createClient(
    cfg.supabaseUrl,
    cfg.supabaseAnonKey
  );

  return supabaseClient;
}

/* =========================
   공통 API Fetch (토큰 포함)
========================= */
async function apiFetch(url, options = {}) {
  const token = localStorage.getItem("access_token");

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {})
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    ...options,
    headers
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.status);
  }

  return res.json();
}

/* =========================
   개인 코드 검증
========================= */
async function verifyCode(code) {
  if (!code) throw new Error("코드 없음");

  return apiFetch("/api/verify-code", {
    method: "POST",
    body: JSON.stringify({
      code: code   // ✅ 서버와 일치
    })
  });
}

/* =========================
   로그아웃
========================= */
function logout() {
  localStorage.clear();
  location.href = "/login";
}
