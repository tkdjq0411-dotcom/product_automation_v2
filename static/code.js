document.getElementById("f").addEventListener("submit", async (e) => {
  e.preventDefault();
  const code = document.getElementById("code").value.trim();
  const err = document.getElementById("err");
  err.textContent = "";

  if (!code) {
    err.textContent = "개인코드를 입력하세요.";
    return;
  }

  const res = await fetch("/api/code/verify", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    credentials: "same-origin",
    body: JSON.stringify({code})
  });

  if (!res.ok) {
    err.textContent = "인증 실패";
    return;
  }

  location.href = "/static/admin_dashboard.html";
});
