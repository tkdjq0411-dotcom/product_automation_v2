// ===============================
// Token utils
// ===============================
function getAccessToken() {
  return localStorage.getItem("access_token");
}

function setAccessToken(token) {
  localStorage.setItem("access_token", token);
}

function clearAuth() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("verified");
  window.location.href = "/login";
}

// ===============================
// apiFetch (모든 인증 요청은 이걸로)
// ===============================
async function apiFetch(url, options = {}) {
  const token = getAccessToken();

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    ...options,
    headers,
  });

  // 토큰 만료 / 인증 실패 공통 처리
  if (res.status === 401) {
    clearAuth();
    throw new Error("Unauthorized");
  }

  return res;
}

// ===============================
// Login handler
// ===============================
async function login(email, password) {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || "로그인 실패");
  }

  setAccessToken(data.access_token);

  // 개인 코드 인증 단계로 이동
  window.location.href = "/code";
}

// ===============================
// Logout
// ===============================
function logout() {
  clearAuth();
}

// ===============================
// Page guards
// ===============================
async function requireAuth() {
  const token = getAccessToken();
  if (!token) {
    clearAuth();
  }
}
