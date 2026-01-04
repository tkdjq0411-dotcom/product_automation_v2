function navHtml(active) {
  const link = (href, label, key) =>
    `<a href="${href}" class="${active === key ? "active" : ""}">${label}</a>`;

  return `
  <nav>
    <div class="container">
      <div><b>ADMIN</b> <span class="small">product_automation_v2</span></div>
      <div class="nav-links">
        ${link("/static/admin_dashboard.html","Dashboard","dashboard")}
        ${link("/static/admin_overview.html","Overview","overview")}
        ${link("/static/admin_items.html","Items","items")}
        ${link("/static/admin_decisions.html","Decisions","decisions")}
        ${link("/static/admin_settings.html","Settings","settings")}
        ${link("/static/admin_analytics.html","Analytics","analytics")}
        ${link("/static/admin_watch.html","Watch","watch")}
      </div>
    </div>
  </nav>`;
}

function mountNav(activeKey) {
  document.body.insertAdjacentHTML("afterbegin", navHtml(activeKey));
}

async function api(path, opts = {}) {
  const res = await fetch(path, { credentials: "same-origin", ...opts });

  if (res.status === 401) {
    location.href = "/static/code.html";
    return;
  }

  const text = await res.text();
  let data = null;
  try { data = JSON.parse(text); } catch { data = { raw: text }; }

  if (!res.ok) {
    const msg = data?.detail ? JSON.stringify(data.detail) : text;
    throw new Error(msg);
  }
  return data;
}

function pct(x) {
  return (Number(x || 0) * 100).toFixed(2) + "%";
}

function esc(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
