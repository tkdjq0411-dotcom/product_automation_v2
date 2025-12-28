// static/common.js

function showToast(message, type = "error") {
  const toast = document.createElement("div")
  toast.innerText = message

  toast.style.position = "fixed"
  toast.style.bottom = "20px"
  toast.style.left = "50%"
  toast.style.transform = "translateX(-50%)"
  toast.style.padding = "12px 20px"
  toast.style.borderRadius = "6px"
  toast.style.color = "#fff"
  toast.style.zIndex = "9999"
  toast.style.fontSize = "14px"
  toast.style.boxShadow = "0 2px 10px rgba(0,0,0,0.2)"

  toast.style.background =
    type === "error" ? "#e74c3c" : "#2ecc71"

  document.body.appendChild(toast)

  setTimeout(() => {
    toast.remove()
  }, 2500)
}
