async function apiFetch(url, options = {}) {
  const token = localStorage.getItem("access_token");

  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem("access_token");
    alert("세션이 만료되었습니다. 다시 로그인하세요.");
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  return res;
}

function logout() {
  localStorage.removeItem("access_token");
  window.location.href = "/login";
}
