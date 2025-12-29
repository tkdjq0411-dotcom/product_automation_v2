console.log("🔥 COMMON_V3 LOADED - NO SUPABASE 🔥");

async function verifyCodeFromPage() {
  const input = document.getElementById("code-input");

  if (!input) {
    alert("코드 입력창을 찾을 수 없습니다");
    return;
  }

  const code = input.value.trim();
  if (!code) {
    alert("코드를 입력하세요");
    return;
  }

  const res = await fetch("/api/verify-code", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code })
  });

  if (!res.ok) {
    alert("인증 실패");
    return;
  }

  const result = await res.json();

  if (result.role === "admin") {
    location.href = "/admin";
  } else {
    location.href = "/user";
  }
}

window.verifyCodeFromPage = verifyCodeFromPage;

