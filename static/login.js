async function login() {
  const code = document.getElementById("code").value;
  const res = await fetch("/api/login", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ code })
  });

  if(res.ok) location.href = "/static/admin_dashboard.html";
  else alert("실패");
}
