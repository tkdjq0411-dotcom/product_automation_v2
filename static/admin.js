console.log("admin.js loaded");

async function initAdmin() {
  const session = await window.getSessionOrGoLogin();
  document.getElementById("who").innerText = `로그인: ${session.user.email}`;

  const cfg = await window.getPublicConfig();
  const marketSel = document.getElementById("market");
  marketSel.innerHTML = "";
  cfg.markets.forEach(m => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    marketSel.appendChild(opt);
  });

  await loadSettings();
  await loadItems();
}

async function loadSettings() {
  const token = await window.getAccessTokenOrThrow();
  const res = await fetch("/api/admin/settings", {
    headers: { "Authorization": `Bearer ${token}` }
  });

  const msg = document.getElementById("settings_msg");
  msg.textContent = "";

  if (!res.ok) {
    msg.textContent = "❌ 설정 불러오기 실패(권한 확인)";
    return;
  }

  const data = await res.json();
  document.getElementById("min_profit").value = data.min_profit;
  document.getElementById("safety_buffer_rate").value = data.safety_buffer_rate;
}

async function saveSettings() {
  const token = await window.getAccessTokenOrThrow();
  const min_profit = parseInt(document.getElementById("min_profit").value || "500");
  const safety_buffer_rate = parseFloat(document.getElementById("safety_buffer_rate").value || "0.01");

  const res = await fetch("/api/admin/set-settings", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify({ min_profit, safety_buffer_rate })
  });

  const msg = document.getElementById("settings_msg");
  if (!res.ok) {
    msg.textContent = "❌ 저장 실패(값 확인)";
    return;
  }
  msg.textContent = "✅ 저장 완료";
  await loadItems();
}

async function addItem() {
  const token = await window.getAccessTokenOrThrow();

  const payload = {
    url: document.getElementById("url").value.trim(),
    buy_price: parseInt(document.getElementById("buy_price").value || "0"),
    sell_price: parseInt(document.getElementById("sell_price").value || "0"),
    shipping_fee: parseInt(document.getElementById("shipping_fee").value || "0"),
    market: document.getElementById("market").value,
    tax_type: document.getElementById("tax_type").value,
  };

  const res = await fetch("/api/admin/items", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify(payload)
  });

  const msg = document.getElementById("add_msg");
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    msg.textContent = "❌ 추가 실패: " + (t || "입력값 확인");
    return;
  }

  const data = await res.json();
  const it = data.item;
  msg.textContent =
    `✅ 저장됨 | 판정=${it.decision} | 순이익=${it.profit} | 수수료=${it.commission_fee} | VAT=${it.vat_fee}`;

  document.getElementById("url").value = "";
  document.getElementById("buy_price").value = "";
  document.getElementById("sell_price").value = "";
  document.getElementById("shipping_fee").value = "0";

  await loadItems();
}

function colorDecision(decision) {
  return decision === "SELL" ? "green" : "red";
}

async function loadItems() {
  const token = await window.getAccessTokenOrThrow();
  const res = await fetch("/api/admin/items", {
    headers: { "Authorization": `Bearer ${token}` }
  });

  const wrap = document.getElementById("items");
  if (!res.ok) {
    wrap.innerHTML = "<p style='color:red'>불러오기 실패(권한/로그인 확인)</p>";
    return;
  }

  const data = await res.json();
  const rows = data.items || [];

  wrap.innerHTML = rows.map(it => `
    <div style="padding:8px; border:1px solid #ddd; margin:6px 0;">
      <div><b>#${it.id}</b> [${it.market}/${it.tax_type}] ${it.url || ""}</div>
      <div>매입 ${it.buy_price} / 판매 ${it.sell_price} / 배송 ${it.shipping_fee}</div>
      <div>
        <b style="color:${colorDecision(it.decision)}">${it.decision}</b>
        | 순이익 ${it.profit}
        | 수수료율 ${Number(it.commission_rate).toFixed(4)}
        | 수수료 ${it.commission_fee}
        | VAT ${it.vat_fee}
        | ${it.reason}
      </div>
    </div>
  `).join("");
}

window.saveSettings = saveSettings;
window.addItem = addItem;
window.loadItems = loadItems;

initAdmin();
