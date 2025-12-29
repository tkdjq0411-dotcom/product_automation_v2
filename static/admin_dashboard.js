console.log("admin_dashboard.js loaded");

async function loadDashboard() {
  const token = await window.getAccessTokenOrThrow();

  const res = await fetch("/api/admin/dashboard", {
    headers: { "Authorization": `Bearer ${token}` }
  });

  if (!res.ok) {
    alert("대시보드 로드 실패(권한/로그인 확인)");
    return;
  }

  const data = await res.json();

  document.getElementById("rule").innerText =
    `SELL 기준 순이익: ${data.min_profit}원 | 안전버퍼: ${data.safety_buffer_rate}`;

  document.getElementById("total").innerText = data.total;
  document.getElementById("sell").innerText = data.sell;
  document.getElementById("stop").innerText = data.stop;

  const tbody = document.getElementById("rows");
  tbody.innerHTML = "";

  for (const it of (data.items || [])) {
    const color = it.decision === "SELL" ? "green" : "red";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${it.id}</td>
      <td>${it.market}</td>
      <td>${it.tax_type}</td>
      <td>${it.profit}</td>
      <td style="color:${color}; font-weight:bold;">${it.decision}</td>
      <td>${it.reason}</td>
      <td style="max-width:420px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
        ${(it.url || "")}
      </td>
    `;
    tbody.appendChild(tr);
  }
}

loadDashboard();

