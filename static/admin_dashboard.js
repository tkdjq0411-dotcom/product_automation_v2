mountNav("dashboard");

async function main() {
  try {
    const s = await api("/api/admin/stats");
    document.getElementById("total").textContent = s.total;
    document.getElementById("sell").textContent = s.sell;
    document.getElementById("stop").textContent = s.stop;
    document.getElementById("avg").textContent = pct(s.avg_margin_rate || 0);
  } catch (e) {}

  try {
    const r = await api("/api/admin/recent-decisions");
    const tbody = document.getElementById("body");
    tbody.innerHTML = "";
    for (const it of (r.items || [])) {
      const d = it.decision || "-";
      const cls = d === "SELL" ? "sell" : (d === "STOP" ? "stop" : "");
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${it.id}</td>
        <td>${esc(it.name||"")}</td>
        <td><span class="badge ${cls}">${d}</span></td>
        <td>${it.profit ?? ""}</td>
        <td>${pct(it.margin_rate||0)}</td>
        <td class="small">${esc(it.reason||"")}</td>
      `;
      tbody.appendChild(tr);
    }
  } catch (e) {
    document.getElementById("err").textContent = "최근 판정 로드 실패";
  }

  document.getElementById("logout").addEventListener("click", async () => {
    await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
    location.href = "/static/code.html";
  });
}

main();
