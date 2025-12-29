console.log("admin.js loaded");

function fmt(n) {
  if (n === null || n === undefined) return "-";
  return String(n);
}

function decColor(dec) {
  return dec === "SELL" ? "green" : "red";
}

async function initAdmin() {
  const session = await window.getSessionOrGoLogin();
  document.getElementById("who").innerText = `로그인: ${session.user.email}`;

  const cfg = await window.getPublicConfig();

  // 마켓 목록
  const marketSel = document.getElementById("market");
  marketSel.innerHTML = "";
  cfg.markets.forEach(m => {
    const opt = document.createElement("option");
    opt.value = m;
    opt.textContent = m;
    marketSel.appendChild(opt);
  });

  marketSel.addEventListener("change", async () => {
    await loadCategories(marketSel.value);
  });

  await loadSettings();
  await loadCategories(marketSel.value);
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
}

async function generateAccessCode() {
  const token = await window.getAccessTokenOrThrow();
  const role = document.getElementById("code_role").value;

  const res = await fetch("/api/admin/generate-access-code", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify({ role })
  });

  const el = document.getElementById("gen_code");
  el.textContent = "";
  if (!res.ok) {
    el.textContent = " ❌ 발급 실패";
    return;
  }
  const data = await res.json();
  el.textContent = ` ✅ 발급됨(${data.role}) : ${data.access_code}  (이 코드 1회용)`;
}

async function loadCategories(market) {
  const token = await window.getAccessTokenOrThrow();
  const res = await fetch(`/api/admin/fee-categories?market=${encodeURIComponent(market)}`, {
    headers: { "Authorization": `Bearer ${token}` }
  });

  const sel = document.getElementById("category");
  sel.innerHTML = "";

  if (!res.ok) {
    // fallback
    ["unknown"].forEach(c => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      sel.appendChild(opt);
    });
    return;
  }

  const data = await res.json();
  (data.categories || ["unknown"]).forEach(c => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    sel.appendChild(opt);
  });
}

async function analyzeUrl() {
  const token = await window.getAccessTokenOrThrow();
  const url = document.getElementById("url").value.trim();
  const msg = document.getElementById("analyze_msg");
  msg.textContent = "";

  if (!url) {
    msg.textContent = " URL 입력 필요";
    return;
  }

  const res = await fetch("/api/admin/analyze-url", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify({ url })
  });

  if (!res.ok) {
    msg.textContent = " ❌ 분석 실패(차단/URL 확인)";
    return;
  }

  const data = await res.json();
  msg.textContent = ` ✅ 마켓감지=${data.market} / 상품명=${data.name_guess ? "OK" : "미검출"}`;

  // 마켓 자동 선택
  const marketSel = document.getElementById("market");
  marketSel.value = data.market;
  await loadCategories(data.market);

  // 상품명 자동 채우기(있으면)
  if (data.name_guess) {
    document.getElementById("name").value = data.name_guess;
  }
}

async function addItem() {
  const token = await window.getAccessTokenOrThrow();

  const payload = {
    url: document.getElementById("url").value.trim(),
    name: document.getElementById("name").value.trim(),
    market: document.getElementById("market").value,
    category: document.getElementById("category").value,
    tax_type: document.getElementById("tax_type").value,
    buy_price: parseInt(document.getElementById("buy_price").value || "0"),
    sell_price: parseInt(document.getElementById("sell_price").value || "0"),
    shipping_fee: parseInt(document.getElementById("shipping_fee").value || "0"),
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
  msg.textContent = "";

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    msg.textContent = "❌ 추가 실패: " + (t || "입력값 확인");
    return;
  }

  const data = await res.json();
  const it = data.item;

  msg.textContent =
    `✅ 저장됨 | ${it.decision} | 순이익=${it.profit} | 마진율=${Number(it.margin_rate).toFixed(4)} | 총비용=${it.total_cost} | 수수료=${it.commission_fee} | VAT=${it.vat_fee}`;

  await loadItems();
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
    <div style="padding:10px; border:1px solid #ddd; margin:8px 0;">
      <div><b>#${it.id}</b> <b>${it.name || ""}</b> [${it.market}/${it.category}/${it.tax_type}]</div>
      <div>매입 ${fmt(it.buy_price)} / 판매 ${fmt(it.sell_price)} / 배송 ${fmt(it.shipping_fee)}</div>
      <div>
        <b style="color:${decColor(it.decision)}">${it.decision}</b>
        | 순이익 ${fmt(it.profit)}
        | 마진율 ${Number(it.margin_rate).toFixed(4)}
        | 총비용 ${fmt(it.total_cost)}
        | 수수료율 ${Number(it.commission_rate).toFixed(6)}
        | 수수료 ${fmt(it.commission_fee)}
        | VAT ${fmt(it.vat_fee)}
        | ${it.reason}
      </div>
      ${it.url ? `<div>URL: <a href="${it.url}" target="_blank">${it.url}</a></div>` : ""}
    </div>
  `).join("");
}

window.saveSettings = saveSettings;
window.generateAccessCode = generateAccessCode;
window.analyzeUrl = analyzeUrl;
window.addItem = addItem;
window.loadItems = loadItems;

initAdmin();
