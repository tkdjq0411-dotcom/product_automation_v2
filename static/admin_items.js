mountNav("items");

async function refresh() {
  const tbody = document.getElementById("tbody");
  const msg = document.getElementById("msg");
  const err = document.getElementById("err");
  err.textContent = "";
  msg.textContent = "로딩중...";

  try {
    const data = await api("/api/admin/items");
    const items = data.items || [];
    tbody.innerHTML = "";
    for (const it of items) {
      const d = it.decision || "-";
      const cls = d === "SELL" ? "sell" : (d === "STOP" ? "stop" : "");
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${it.id}</td>
        <td>${esc(it.name||"")}</td>
        <td>${esc(it.market||"")}</td>
        <td><span class="badge ${cls}">${d}</span></td>
        <td><button data-id="${it.id}">삭제</button></td>
      `;
      tbody.appendChild(tr);
    }
    tbody.querySelectorAll("button[data-id]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        await api(`/api/admin/items/${id}`, { method: "DELETE" });
        refresh();
      });
    });
    msg.textContent = `총 ${items.length}개`;
  } catch (e) {
    err.textContent = "로드 실패: " + e.message;
    msg.textContent = "";
  }
}

document.getElementById("refresh").addEventListener("click", refresh);

document.getElementById("add").addEventListener("click", async () => {
  const err = document.getElementById("err");
  const msg = document.getElementById("msg");
  err.textContent = "";
  msg.textContent = "";

  const payload = {
    name: document.getElementById("name").value.trim(),
    market: document.getElementById("market").value,
    category: (document.getElementById("category").value.trim() || "unknown"),
    tax_type: document.getElementById("tax_type").value,
    buy_price: document.getElementById("buy_price").value,
    sell_price: document.getElementById("sell_price").value,
    shipping_fee: document.getElementById("shipping_fee").value,
  };

  try {
    await api("/api/admin/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    msg.textContent = "추가 완료 (현재는 틀: 더미 저장)";
    refresh();
  } catch (e) {
    err.textContent = "추가 실패: " + e.message;
  }
});

refresh();
