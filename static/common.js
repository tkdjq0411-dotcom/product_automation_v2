console.log("common.js loaded");

let _cfg = null;
let _sb = null;

async function getPublicConfig() {
  if (_cfg) return _cfg;
  const res = await fetch("/api/public-config");
  _cfg = await res.json();
  return _cfg;
}

async function ensureSupabaseLoaded() {
  if (window.supabase) return;
  await new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2";
    s.onload = resolve;
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

async function getSupabase() {
  if (_sb) return _sb;

  const cfg = await getPublicConfig();
  await ensureSupabaseLoaded();

  _sb = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
  return _sb;
}

async function getSessionOrGoLogin() {
  const sb = await getSupabase();
  const { data } = await sb.auth.getSession();
  if (!data?.session) {
    location.href = "/login";
    throw new Error("No session");
  }
  return data.session;
}

async function getAccessTokenOrThrow() {
  const session = await getSessionOrGoLogin();
  const token = session?.access_token;
  if (!token) {
    location.href = "/login";
    throw new Error("No token");
  }
  return token;
}

// login.html
async function login() {
  const sb = await getSupabase();
  const email = document.getElementById("email")?.value?.trim();
  const password = document.getElementById("password")?.value?.trim();
  const msg = document.getElementById("msg");
  if (msg) msg.textContent = "";

  const { error } = await sb.auth.signInWithPassword({ email, password });
  if (error) {
    if (msg) msg.textContent = "❌ 로그인 실패: " + error.message;
    return;
  }

  if (msg) msg.textContent = "✅ 로그인 성공";
  location.href = "/code";
}

// code.html
async function verifyAccessCode() {
  const code = document.getElementById("access_code")?.value?.trim();
  const msg = document.getElementById("msg");
  if (msg) msg.textContent = "";

  if (!code) {
    if (msg) msg.textContent = "코드를 입력하세요";
    return;
  }

  const token = await getAccessTokenOrThrow();

  const res = await fetch("/api/verify-access-code", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify({ code })
  });

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    if (msg) msg.textContent = "❌ 개인코드 인증 실패: " + (t || "권한/코드 확인");
    return;
  }

  const data = await res.json();
  localStorage.setItem("role", data.role);

  if (data.role === "admin") location.href = "/admin";
  else location.href = "/user";
}

window.getPublicConfig = getPublicConfig;
window.getSupabase = getSupabase;
window.getSessionOrGoLogin = getSessionOrGoLogin;
window.getAccessTokenOrThrow = getAccessTokenOrThrow;
window.login = login;
window.verifyAccessCode = verifyAccessCode;

