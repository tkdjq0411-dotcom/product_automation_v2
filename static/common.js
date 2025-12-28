// ==============================
// Supabase 전역 (중복 선언 방지)
// ==============================
if (!window._supabaseClient) {
  window._supabaseClient = { client: null };
}

// ==============================
// Supabase 초기화
// ==============================
async function initSupabase() {
  if (window._supabaseClient.client) return;

  const res = await fetch("/api/public-config");
  const cfg = await res.json();

  window._supabaseClient.client = window.supabase.createClient(
    cfg.supabaseUrl,
    cfg.supabaseAnonKey
  );
}

// ==============================
// 공통 API fetch
// ==============================
async function apiFetch(url, options = {}) {
  await initSupabase();
  const supabase = window._supabaseClient.client;

  const {
    data: { session }
  } = await supabase.auth.getSession();

  if (!session) {
    throw new Error("로그인이 필요합니다");
  }

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${session.access_token}`,
      ...(options.headers || {})
    }
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "요청 실패");
  }

  return data;
}

// ==============================
// ⭐ 개인 코드 검증 (전역 노출)
// ==============================
window.verifyCode = async function (code) {
  return apiFetch("/api/verify-code", {
    method: "POST",
    body: JSON.stringify({ code })
  });
};

// ==============================
// 로그아웃
// ==============================
window.logout = async function () {
  await initSupabase();
  await window._supabaseClient.client.auth.signOut();
  location.href = "/login";
};

