mountNav("decisions");

document.getElementById("load").addEventListener("click", async () => {
  const err = document.getElementById("err");
  const tbody = document.getElementById("tbody");
  err.textContent = "";
  tbody.innerHTML = "";

  try {
    const data = await api("/api/admin/decision-logs");
    const logs = data.logs || [];
    for (const lg of logs) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${esc(lg.created_at||"")}</td>
        <td>${esc(lg.item_id||"")}</td>
        <td>${esc(lg.prev_decision||"")}</td>
        <td>${esc(lg.new_decision||"")}</td>
        <td>${esc(lg.profit||"")}</td>
        <td class="small">${esc(lg.reason||"")}</td>
      `;
      tbody.appendChild(tr);
    }
  } catch (e) {
    err.textContent = "로드 실패: " + e.message;
  }
});
