mountNav("analytics");

document.getElementById("load").addEventListener("click", async () => {
  const err = document.getElementById("err");
  err.textContent = "";
  try {
    await api("/api/admin/analytics");
    alert("로드(틀) 완료");
  } catch (e) {
    err.textContent = "로드 실패: " + e.message;
  }
});
