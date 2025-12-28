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
// 공통 API fetch (JSON 반환)
// ==============================
async function apiFetch(url, options = {}) {
  await initSupabase();
  const supabase = window._supabaseClient.client;

  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw new Error("로그인이 필요합니다");
  }

  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...(options.headers || {}),
    },
  });

  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    // JSON 아닌 응답 대비
  }

  if (!res.ok) {
    const msg = (data && (data.detail || data.message)) || "요청 실패";
    throw new Error(msg);
  }

  return data;
}

// 전역 노출
window.initSupabase = initSupabase;
window.apiFetch = apiFetch;

// ==============================
// 개인 코드 검증
// ==============================
window.verifyCode = async function (code) {
  return apiFetch("/api/verify-code", {
    method: "POST",
    body: JSON.stringify({ code }),
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
