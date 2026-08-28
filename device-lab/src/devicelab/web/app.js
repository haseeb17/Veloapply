const $ = (sel, root = document) => root.querySelector(sel);
const view = $("#view");
const title = $("#title");
const kicker = $("#kicker");
const dialog = $("#run-dialog");

const state = {
  devices: [],
  jobs: [],
  pools: [],
  sessions: [],
  overview: null,
  audit: [],
  use: null,
  filter: { q: "", pool: "", status: "" },
};

function operator() {
  return $("#operator").value.trim() || "lab";
}

async function api(path, opts = {}) {
  const headers = { "X-Operator": operator(), ...(opts.body ? { "Content-Type": "application/json" } : {}), ...opts.headers };
  const res = await fetch(path, { ...opts, headers, body: opts.body ? JSON.stringify(opts.body) : undefined });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function route() {
  const hash = location.hash.replace(/^#/, "") || "/";
  return hash.startsWith("/") ? hash : `/${hash}`;
}

function pill(status) {
  return `<span class="pill ${status || ""}">${status || "unknown"}</span>`;
}

function deviceById(id) {
  return state.devices.find((d) => d.id === id);
}

function renderOverview() {
  const o = state.overview || {};
  title.textContent = "The rack";
  kicker.textContent = "Overview";
  const alerts = o.alerts || [];
  const jobs = o.recent_jobs || [];
  view.innerHTML = `
    <div class="stats">
      <div class="stat"><b>${o.device_count ?? "—"}</b><span>Handsets in inventory</span></div>
      <div class="stat"><b>${o.online ?? 0}</b><span>Idle / ready</span></div>
      <div class="stat"><b>${o.busy ?? 0}</b><span>Running a suite</span></div>
      <div class="stat"><b>${o.reserved ?? 0}</b><span>On a desk session</span></div>
      <div class="stat"><b>${o.running_jobs ?? 0}/${o.queued_jobs ?? 0}</b><span>Runs live / queued</span></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <h2>Recent runs</h2>
        ${jobs.length ? `<table><thead><tr><th>Run</th><th>Suite</th><th>App</th><th>Status</th></tr></thead><tbody>
          ${jobs.map((j) => `<tr>
            <td><a href="#/runs/${j.id}">${esc(j.name)}</a></td>
            <td class="mono">${esc(j.suite)}</td>
            <td class="mono">${esc(j.app_label)}</td>
            <td>${pill(j.status)}</td>
          </tr>`).join("")}
        </tbody></table>` : `<p class="muted">No runs yet. Queue smoke against an app you own.</p>`}
      </div>
      <div class="card">
        <h2>Health</h2>
        ${alerts.length ? alerts.map((a) => `<div class="alert">
          <div><span class="pill ${a.severity}">${a.severity}</span> ${esc(a.title)}</div>
          <div class="muted">${esc(a.detail)}</div>
        </div>`).join("") : `<p class="muted">No thermal, battery, or storage warnings.</p>`}
      </div>
    </div>
  `;
}

function renderRack() {
  title.textContent = "Device rack";
  kicker.textContent = "Inventory";
  const { q, pool, status } = state.filter;
  const rows = state.devices.filter((d) => {
    const blob = `${d.name} ${d.model} ${d.os} ${d.os_version} ${d.serial}`.toLowerCase();
    if (q && !blob.includes(q.toLowerCase())) return false;
    if (pool && d.pool_id !== pool) return false;
    if (status && d.status !== status) return false;
    return true;
  });
  view.innerHTML = `
    <div class="filters">
      <input id="q" placeholder="Search name, serial, OS" value="${esc(q)}" />
      <select id="pool">
        <option value="">All pools</option>
        ${state.pools.map((p) => `<option value="${p.id}" ${p.id === pool ? "selected" : ""}>${esc(p.name)}</option>`).join("")}
      </select>
      <select id="status">
        <option value="">All statuses</option>
        ${["online", "busy", "reserved", "offline", "maintenance"].map((s) => `<option ${s === status ? "selected" : ""}>${s}</option>`).join("")}
      </select>
    </div>
    <div class="rack">
      ${rows.map((d) => `
        <a class="phone" href="#/devices/${d.id}">
          <div class="bezel">
            <div class="os">${esc(d.os)} ${esc(d.os_version)}</div>
            <div>
              <strong>${esc(d.name)}</strong>
              <div>${d.battery}% ${d.charging ? "charging" : ""} · ${d.temperature_c.toFixed(1)}°C</div>
            </div>
            <div>${esc(d.form_factor)} · API ${d.api_level}</div>
          </div>
          <div class="meta">
            ${pill(d.status)}
            <span class="mono">${esc(d.serial.slice(0, 10))}</span>
          </div>
        </a>
      `).join("")}
    </div>
  `;
  $("#q").addEventListener("input", (e) => { state.filter.q = e.target.value; renderRack(); });
  $("#pool").addEventListener("change", (e) => { state.filter.pool = e.target.value; renderRack(); });
  $("#status").addEventListener("change", (e) => { state.filter.status = e.target.value; renderRack(); });
}

function renderDevice(id) {
  const d = deviceById(id);
  if (!d) { title.textContent = "Missing device"; view.innerHTML = ""; return; }
  title.textContent = d.name;
  kicker.textContent = d.serial;
  const jobs = state.jobs.filter((j) => j.device_ids.includes(d.id)).slice(0, 8);
  view.innerHTML = `
    <div class="grid-2">
      <div class="card">
        <p class="lede">${esc(d.manufacturer)} ${esc(d.model)} · ${esc(d.form_factor)} · ${pill(d.status)}</p>
        <table>
          <tr><th>OS</th><td>${esc(d.os)} ${esc(d.os_version)} (API ${d.api_level})</td></tr>
          <tr><th>ABI</th><td class="mono">${esc(d.abi)}</td></tr>
          <tr><th>Battery</th><td>${d.battery}% ${d.charging ? "charging" : "on battery"}</td></tr>
          <tr><th>Thermal</th><td>${d.temperature_c.toFixed(1)}°C</td></tr>
          <tr><th>Storage</th><td>${d.storage_free_gb.toFixed(1)} GB free</td></tr>
          <tr><th>Source</th><td>${esc(d.source)} · ${d.automatable ? "automatable" : "manual only"}</td></tr>
          <tr><th>Tags</th><td>${d.tags.map(esc).join(", ")}</td></tr>
        </table>
        ${d.notes ? `<p class="muted">${esc(d.notes)}</p>` : ""}
        <p>
          <button class="primary" id="reserve" ${d.status === "offline" || d.status === "busy" || d.status === "maintenance" ? "disabled" : ""}>Start desk session</button>
          <button class="ghost" id="maint">${d.status === "maintenance" ? "Return to rack" : "Mark maintenance"}</button>
        </p>
      </div>
      <div class="card">
        <h2>Runs on this device</h2>
        ${jobs.length ? `<ul class="steps">${jobs.map((j) => `<li><a href="#/runs/${j.id}">${esc(j.name)}</a> ${pill(j.status)}</li>`).join("")}</ul>` : `<p class="muted">No automated runs yet.</p>`}
      </div>
    </div>
  `;
  $("#reserve").addEventListener("click", async () => {
    const purpose = prompt("What are you reproducing?") || "manual QA";
    await api("/api/sessions", { method: "POST", body: { device_id: d.id, purpose } });
    await refresh();
    renderDevice(id);
  });
  $("#maint").addEventListener("click", async () => {
    await api(`/api/devices/${d.id}/maintenance`, { method: "POST", body: { enabled: d.status !== "maintenance" } });
    await refresh();
    renderDevice(id);
  });
}

function renderRuns() {
  title.textContent = "Test runs";
  kicker.textContent = "Automation";
  view.innerHTML = `
    <table>
      <thead><tr><th>Name</th><th>Suite</th><th>App</th><th>Devices</th><th>Status</th></tr></thead>
      <tbody>
        ${state.jobs.map((j) => `<tr>
          <td><a href="#/runs/${j.id}">${esc(j.name)}</a></td>
          <td class="mono">${esc(j.suite)}</td>
          <td class="mono">${esc(j.app_label)}</td>
          <td>${j.device_ids.length}</td>
          <td>${pill(j.status)}</td>
        </tr>`).join("")}
      </tbody>
    </table>
  `;
}

function renderRun(id) {
  const j = state.jobs.find((x) => x.id === id);
  if (!j) { title.textContent = "Missing run"; view.innerHTML = ""; return; }
  title.textContent = j.name;
  kicker.textContent = j.suite;
  view.innerHTML = `
    <p class="lede">${pill(j.status)} · ${esc(j.app_label)} · queued by ${esc(j.created_by)}</p>
    ${j.status === "queued" || j.status === "running" ? `<p><button class="ghost" id="cancel">Cancel run</button></p>` : ""}
    ${j.runs.map((r) => {
      const d = deviceById(r.device_id);
      return `<div class="card" style="margin-bottom:14px">
        <h2>${esc(d ? d.name : r.device_id)} ${pill(r.status)}</h2>
        ${r.failure ? `<p class="form-error">${esc(r.failure)}</p>` : ""}
        ${r.visual_match != null ? `<p class="muted">Visual match ${r.visual_match}%</p>` : ""}
        <ul class="steps">
          ${r.steps.map((s) => `<li><span>${esc(s.name)}</span><span>${pill(s.status)} <span class="mono">${s.duration_ms}ms</span></span></li>`).join("")}
        </ul>
        <div class="shot-row">${(r.screenshots || []).map((s) => `<div class="shot">${esc(s.caption)}</div>`).join("")}</div>
        ${r.log_excerpt ? `<pre>${esc(r.log_excerpt)}</pre>` : ""}
      </div>`;
    }).join("")}
  `;
  const cancel = $("#cancel");
  if (cancel) cancel.addEventListener("click", async () => {
    await api(`/api/jobs/${j.id}/cancel`, { method: "POST" });
    await refresh();
    renderRun(id);
  });
}

function renderSessions() {
  title.textContent = "Desk sessions";
  kicker.textContent = "Manual QA";
  view.innerHTML = `
    <p class="lede">Reserve a handset so two people do not debug on the same USB port.</p>
    <table>
      <thead><tr><th>Device</th><th>Operator</th><th>Purpose</th><th>Status</th><th></th></tr></thead>
      <tbody>
        ${state.sessions.map((s) => {
          const d = deviceById(s.device_id);
          return `<tr>
            <td>${esc(d ? d.name : s.device_id)}</td>
            <td>${esc(s.operator)}</td>
            <td>${esc(s.purpose)}</td>
            <td>${pill(s.status)}</td>
            <td>${s.status === "active" ? `<button class="ghost" data-end="${s.id}">Release</button>` : ""}</td>
          </tr>`;
        }).join("")}
      </tbody>
    </table>
  `;
  view.querySelectorAll("[data-end]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await api(`/api/sessions/${btn.dataset.end}/end`, { method: "POST" });
      await refresh();
      render();
    });
  });
}

function renderAudit() {
  title.textContent = "Audit log";
  kicker.textContent = "Who used the rack";
  view.innerHTML = `<table><thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Target</th><th>Detail</th></tr></thead><tbody>
    ${state.audit.map((e) => `<tr>
      <td class="mono">${esc(e.at)}</td>
      <td>${esc(e.actor)}</td>
      <td class="mono">${esc(e.action)}</td>
      <td class="mono">${esc(e.target)}</td>
      <td class="muted">${esc(e.detail)}</td>
    </tr>`).join("")}
  </tbody></table>`;
}

function renderCi() {
  title.textContent = "CI hook";
  kicker.textContent = "From a pipeline";
  view.innerHTML = `
    <div class="card">
      <p class="lede">Dispatch a suite after your app build. Point this at phones you own, and at the package you just built.</p>
      <pre>curl -s http://127.0.0.1:8765/api/jobs \\
  -H 'Content-Type: application/json' \\
  -H 'X-Operator: github-actions' \\
  -d '{
    "name": "post-merge smoke",
    "suite": "smoke",
    "app_label": "com.yourcompany.app",
    "pool_id": "pool-smoke"
  }'</pre>
    </div>
  `;
}

function renderUse() {
  title.textContent = "Acceptable use";
  kicker.textContent = "Scope";
  const use = state.use || { allowed: [], not_this_product: [] };
  view.innerHTML = `
    <div class="grid-2">
      <div class="card">
        <h2>This lab is for</h2>
        <ul>${use.allowed.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      </div>
      <div class="card">
        <h2>Not this product</h2>
        <ul>${use.not_this_product.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
      </div>
    </div>
  `;
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function highlightNav() {
  const path = route();
  document.querySelectorAll(".rail a").forEach((a) => {
    const r = a.getAttribute("data-route");
    a.classList.toggle("active", path === r || (r !== "/" && path.startsWith(r)));
  });
}

function render() {
  highlightNav();
  const path = route();
  const device = path.match(/^\/devices\/([^/]+)/);
  const run = path.match(/^\/runs\/([^/]+)/);
  if (path === "/" ) return renderOverview();
  if (path === "/rack") return renderRack();
  if (device) return renderDevice(device[1]);
  if (path === "/runs") return renderRuns();
  if (run) return renderRun(run[1]);
  if (path === "/sessions") return renderSessions();
  if (path === "/audit") return renderAudit();
  if (path === "/ci") return renderCi();
  if (path === "/use") return renderUse();
  renderOverview();
}

async function refresh() {
  const [overview, devices, jobs, pools, sessions, audit, use] = await Promise.all([
    api("/api/overview"),
    api("/api/devices"),
    api("/api/jobs"),
    api("/api/pools"),
    api("/api/sessions"),
    api("/api/audit"),
    api("/api/use"),
  ]);
  state.overview = overview;
  state.devices = devices.devices;
  state.jobs = jobs.jobs;
  state.pools = pools.pools;
  state.sessions = sessions.sessions;
  state.audit = audit.events;
  state.use = use;
}

$("#new-run").addEventListener("click", () => {
  $("#run-error").hidden = true;
  dialog.showModal();
});
$("#cancel-run").addEventListener("click", () => dialog.close());
$("#run-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    const job = await api("/api/jobs", {
      method: "POST",
      body: {
        name: form.get("name"),
        suite: form.get("suite"),
        app_label: form.get("app_label"),
        pool_id: form.get("pool_id"),
        notes: form.get("notes"),
      },
    });
    dialog.close();
    location.hash = `#/runs/${job.job.id}`;
    await refresh();
    render();
  } catch (err) {
    const box = $("#run-error");
    box.hidden = false;
    box.textContent = err.message;
  }
});
$("#sync-adb").addEventListener("click", async () => {
  const result = await api("/api/sync-adb", { method: "POST" });
  await refresh();
  render();
  alert(result.adb ? `USB sync complete (${result.serials.length} device(s))` : "adb is not installed on this machine. Demo rack is unchanged.");
});

window.addEventListener("hashchange", render);

(async function boot() {
  await refresh();
  render();
  setInterval(async () => {
    try {
      const active = document.activeElement;
      const typing = active && ["INPUT", "SELECT", "TEXTAREA"].includes(active.tagName);
      await refresh();
      if (!typing && !dialog.open) render();
    } catch (_) { /* keep last frame */ }
  }, 2000);
})();
