async function login(event) {
  event.preventDefault();
  const error = document.getElementById("login-error");
  error.hidden = true;
  const data = Object.fromEntries(new FormData(event.target));
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Login fail" }));
    error.textContent = body.detail || "Login fail";
    error.hidden = false;
    return;
  }
  window.location.href = "/";
}

document.getElementById("login-form").addEventListener("submit", login);
