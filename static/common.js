c// ==============================
// Supabase 초기화
// ==============================
let supabase;

async function initSupabase() {
  const res = await fetch("/api/public-config");
  const cfg = await res.json();

  supabase = window.supabase.createClient(
    cfg.supabaseUrl,
    cfg.supabaseAnonKey
  );
}

// ==============================
// 공통 API fetch (토큰 자동 포함)
// ==============================
async function apiFetch(url, options = {}) {
  if (!supabase) {
    await initSupabase();
  }

  const {
    data: { session }
  } = await supabase.auth.getSession();

  if (!session) {
    throw new Error("로그인이 필요합니다");
  }

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
    "Authorization": `Bearer ${session.access_token}`
  };

  const res = await fetch(url, {
    ...options,
    headers
  });

  let data;
  try {
    data = await res.json();
  } catch {
    throw new Error("서버 응답이 JSON이 아닙니다");
  }

  if (!res.ok) {
    throw new Error(data.detail || "요청 실패");
  }

  return data;
}

// ==============================
// ⭐ 개인 코드 검증 (중요)
// ==============================
async function verifyCode(code) {
  return apiFetch("/api/verify-code", {
    method: "POST",
    body: JSON.stringify({
      code: code   // ❗❗ 반드시 code
    })
  });
}

// ==============================
// 로그아웃
// ==============================
async function logout() {
  if (!supabase) await initSupabase();
  await supabase.auth.signOut();
  location.href = "/login";
}

