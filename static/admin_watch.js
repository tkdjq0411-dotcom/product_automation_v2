mountNav("watch");

document.getElementById("one").addEventListener("click", async () => {
  const err = document.getElementById("err");
  err.textContent = "";
  const id = document.getElementById("item_id").value.trim();
  if (!id) { err.textContent = "item_id 입력"; return; }
  try {
    await api(`/api/admin/recheck/${id}`, { method: "POST" });
    alert("단건 재계산(틀) 호출 완료");
  } catch (e) { err.textContent = e.message; }
});

document.getElementById("all").addEventListener("click", async () => {
  const err = document.getElementById("err");
  err.textContent = "";
  try {
    await api(`/api/admin/recheck/all`, { method: "POST" });
    alert("전체 재계산(틀) 호출 완료");
  } catch (e) { err.textContent = e.message; }
});
