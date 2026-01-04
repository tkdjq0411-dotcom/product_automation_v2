mountNav("settings");

async function load() {
  const err = document.getElementById("err");
  const msg = document.getElementById("msg");
  err.textContent = "";
  msg.textContent = "";

  try {
    const s = await api("/api/admin/settings");
    document.getElementById("min_profit").value = s.min_profit ?? 500;
    document.getElementById("buffer").value = s.safety_buffer_rate ?? 0.01;
    msg.textContent = "불러오기 완료 (현재는 틀: 더미 저장)";
  } catch (e) {
    err.textContent = "불러오기 실패: " + e.message;
  }
}

async function save() {
  const err = document.getElementById("err");
  const msg = document.getElementById("msg");
  err.textContent = "";
  msg.textContent = "";

  try {
    const payload = {
      min_profit: document.getElementById("min_profit").value,
      safety_buffer_rate: document.getElementById("buffer").value
    };
    await api("/api/admin/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    msg.textContent = "저장 완료";
  } catch (e) {
    err.textContent = "저장 실패: " + e.message;
  }
}

document.getElementById("load").addEventListener("click", load);
document.getElementById("save").addEventListener("click", save);
load();
