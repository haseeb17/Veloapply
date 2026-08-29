function beep(ok) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "square";
  osc.frequency.value = ok ? 880 : 240;
  gain.gain.value = 0.05;
  osc.connect(gain).connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + 0.12);
}

function tick() {
  const el = document.getElementById("clock");
  el.textContent = new Date().toLocaleTimeString("en-PK", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

async function scanUid(uid) {
  const flash = document.getElementById("flash");
  const res = await fetch("/api/scan", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uid, source: "kiosk" }),
  });
  if (res.status === 401) {
    window.location.href = "/login";
    return;
  }
  const data = await res.json();
  flash.hidden = false;
  flash.className = "flash " + (data.status || "unknown");
  const st = data.student;
  flash.innerHTML = `
    <h2>${data.title}</h2>
    <p>${data.message}</p>
    ${st ? `<p>${st.class_label} · ${st.roll_no} · ${st.rfid_uid}</p>` : `<p>UID ${data.uid}</p>`}
  `;
  beep(data.ok && data.status !== "unknown");
}

async function boot() {
  tick();
  setInterval(tick, 1000);
  const me = await fetch("/api/me", { credentials: "same-origin" });
  if (me.status === 401) {
    window.location.href = "/login";
    return;
  }
  const payload = await me.json();
  document.getElementById("kiosk-school").textContent = payload.settings.school_name || "Hazri";

  const form = document.getElementById("scan-form");
  const input = document.getElementById("uid");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const uid = input.value.trim();
    if (!uid) return;
    input.value = "";
    await scanUid(uid);
    input.focus();
  });
  window.addEventListener("click", () => input.focus());

  const cards = await fetch("/api/demo-cards", { credentials: "same-origin" }).then((r) => r.json());
  document.getElementById("demo-cards").innerHTML = cards.cards
    .map(
      (c) => `<button class="chip" data-uid="${c.rfid_uid}">
        <strong>${c.name}</strong>
        <small>${c.class_name}-${c.section} · ${c.rfid_uid}</small>
      </button>`
    )
    .join("");
  document.getElementById("demo-cards").onclick = (e) => {
    const btn = e.target.closest("[data-uid]");
    if (!btn) return;
    scanUid(btn.dataset.uid);
  };
}

boot();
