const state = {
  user: null,
  settings: {},
  page: "dashboard",
  classes: [],
};

async function api(path, options = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("auth");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || "Request failed");
  }
  if (res.headers.get("content-type")?.includes("text/csv")) return res;
  return res.json();
}

function money(n) {
  return "PKR " + Number(n).toLocaleString("en-PK");
}

function clock(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("en-PK", { hour: "2-digit", minute: "2-digit" });
}

function badge(status, late) {
  if (late) return `<span class="badge late">Late</span>`;
  const map = {
    present: "Present",
    absent: "Absent",
    late: "Late",
    out: "Out",
    unknown: "Unknown",
    ok: "OK",
  };
  return `<span class="badge ${status || "absent"}">${map[status] || status || "Absent"}</span>`;
}

function showPage(name) {
  if (name === "kiosk-link") {
    window.location.href = "/kiosk";
    return;
  }
  state.page = name;
  document.querySelectorAll(".page").forEach((el) => {
    el.hidden = el.id !== `page-${name}`;
  });
  document.querySelectorAll(".nav nav button").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.page === name);
  });
  const loaders = {
    dashboard: loadDashboard,
    students: loadStudents,
    attendance: loadAttendance,
    reports: loadReports,
    sms: loadSms,
    pricing: loadPricing,
    settings: loadSettings,
  };
  loaders[name]?.();
}

function modal(html) {
  const root = document.getElementById("modal");
  root.innerHTML = `<div class="sheet">${html}</div>`;
  root.hidden = false;
  root.onclick = (e) => {
    if (e.target === root) root.hidden = true;
  };
}

async function loadDashboard() {
  const data = await api("/api/dashboard");
  const t = data.totals;
  const bars = data.by_class
    .map((c) => {
      const pct = c.total ? Math.round((c.present / c.total) * 100) : 0;
      return `<div class="bar"><span>${c.name}-${c.section}</span><i><span style="width:${pct}%"></span></i><b>${pct}%</b></div>`;
    })
    .join("");
  const recent = data.recent
    .map(
      (r) => `<tr>
        <td>${r.student_name || "Unknown card"}</td>
        <td>${r.class_name ? `${r.class_name}-${r.section}` : r.rfid_uid}</td>
        <td>${r.event_type}</td>
        <td>${badge(r.status)}</td>
        <td>${clock(r.created_at)}</td>
      </tr>`
    )
    .join("");
  document.getElementById("page-dashboard").innerHTML = `
    <h1>Aaj ki hazri</h1>
    <p class="sub">${data.school} · ${data.city} · ${data.day}</p>
    <div class="stats">
      <div class="stat"><span>Students</span><b>${t.students}</b></div>
      <div class="stat present"><span>Present</span><b>${t.present}</b></div>
      <div class="stat late"><span>Late</span><b>${t.late}</b></div>
      <div class="stat absent"><span>Absent</span><b>${t.absent}</b></div>
    </div>
    <div class="grid-2" style="margin-top:1rem">
      <div class="panel">
        <h3>Class-wise</h3>
        <div class="bars">${bars}</div>
      </div>
      <div class="panel">
        <h3>Latest taps</h3>
        <table><thead><tr><th>Name</th><th>Class</th><th>In/Out</th><th>Status</th><th>Time</th></tr></thead>
        <tbody>${recent}</tbody></table>
      </div>
    </div>
  `;
}

async function loadClasses() {
  const data = await api("/api/classes");
  state.classes = data.classes;
  return data.classes;
}

function classOptions(selected) {
  return state.classes
    .map(
      (c) =>
        `<option value="${c.id}" ${String(c.id) === String(selected) ? "selected" : ""}>${c.name}-${c.section}</option>`
    )
    .join("");
}

async function loadStudents() {
  await loadClasses();
  const data = await api("/api/students");
  const rows = data.students
    .map(
      (s) => `<tr>
        <td>${s.name}</td>
        <td>${s.roll_no}</td>
        <td>${s.class_label}</td>
        <td class="uid">${s.rfid_uid}</td>
        <td>${s.parent_name}<br><small>${s.parent_phone}</small></td>
        <td>${s.active ? badge("present") : badge("absent")}</td>
        <td><button class="secondary" data-edit="${s.id}">Edit</button></td>
      </tr>`
    )
    .join("");
  const cards = data.students
    .slice(0, 24)
    .map(
      (s) => `<article class="id-card">
        <strong>${s.name}</strong>
        <div>${s.class_label} · ${s.roll_no}</div>
        <div class="uid">${s.rfid_uid}</div>
        <small>Wali: ${s.parent_phone || "—"}</small>
      </article>`
    )
    .join("");
  document.getElementById("page-students").innerHTML = `
    <h1>Students & chip cards</h1>
    <p class="sub">Har card ka UID unique hona chahiye. USB reader tap par yahi number type karta hai.</p>
    <div class="toolbar">
      <input id="student-q" placeholder="Name, roll, card, phone" />
      <select id="student-class"><option value="">All classes</option>${classOptions()}</select>
      <button class="primary" id="add-student">Add student</button>
      <button class="secondary" onclick="window.print()">Print ID cards</button>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>Name</th><th>Roll</th><th>Class</th><th>Card UID</th><th>Parent</th><th>Status</th><th></th></tr></thead>
        <tbody id="student-rows">${rows}</tbody>
      </table>
    </div>
    <h2>Printable cards</h2>
    <div class="id-sheet">${cards}</div>
  `;
  document.getElementById("add-student").onclick = () => studentForm();
  document.getElementById("student-q").oninput = filterStudents;
  document.getElementById("student-class").onchange = filterStudents;
  document.getElementById("student-rows").onclick = (e) => {
    const id = e.target.dataset.edit;
    if (!id) return;
    const student = data.students.find((s) => String(s.id) === String(id));
    studentForm(student);
  };
}

async function filterStudents() {
  const q = document.getElementById("student-q").value;
  const classId = document.getElementById("student-class").value;
  const qs = new URLSearchParams();
  if (q) qs.set("q", q);
  if (classId) qs.set("class_id", classId);
  const data = await api("/api/students?" + qs.toString());
  document.getElementById("student-rows").innerHTML = data.students
    .map(
      (s) => `<tr>
        <td>${s.name}</td><td>${s.roll_no}</td><td>${s.class_label}</td>
        <td>${s.rfid_uid}</td><td>${s.parent_phone}</td>
        <td>${s.active ? "Active" : "Left"}</td>
        <td><button class="secondary" data-edit="${s.id}">Edit</button></td>
      </tr>`
    )
    .join("");
}

function studentForm(student) {
  modal(`
    <h3>${student ? "Edit student" : "New student"}</h3>
    <form id="student-form">
      <label>Name <input name="name" required value="${student?.name || ""}" /></label>
      <div class="row-2">
        <label>Roll no <input name="roll_no" required value="${student?.roll_no || ""}" /></label>
        <label>Class <select name="class_id">${classOptions(student?.class_id)}</select></label>
      </div>
      <label>Chip / RFID UID <input name="rfid_uid" required value="${student?.rfid_uid || ""}" placeholder="HAZRI-2001" /></label>
      <div class="row-2">
        <label>Parent <input name="parent_name" value="${student?.parent_name || ""}" /></label>
        <label>Phone <input name="parent_phone" value="${student?.parent_phone || ""}" placeholder="03xx-xxxxxxx" /></label>
      </div>
      <label>Gender
        <select name="gender">
          <option ${student?.gender === "male" ? "selected" : ""}>male</option>
          <option ${student?.gender === "female" ? "selected" : ""}>female</option>
          <option ${!student || student?.gender === "other" ? "selected" : ""}>other</option>
        </select>
      </label>
      <div class="actions">
        <button type="button" class="secondary" id="cancel">Cancel</button>
        <button class="primary">Save</button>
      </div>
    </form>
  `);
  document.getElementById("cancel").onclick = () => (document.getElementById("modal").hidden = true);
  document.getElementById("student-form").onsubmit = async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target));
    body.class_id = Number(body.class_id);
    body.active = true;
    const path = student ? `/api/students/${student.id}` : "/api/students";
    await api(path, { method: student ? "PUT" : "POST", body: JSON.stringify(body) });
    document.getElementById("modal").hidden = true;
    loadStudents();
  };
}

async function loadAttendance() {
  await loadClasses();
  const data = await api("/api/attendance");
  renderAttendance(data);
}

function renderAttendance(data) {
  const rows = data.rows
    .map(
      (r) => `<tr>
        <td>${r.name}</td>
        <td>${r.roll_no}</td>
        <td>${r.class_name}-${r.section}</td>
        <td>${clock(r.check_in)}</td>
        <td>${clock(r.check_out)}</td>
        <td>${badge(r.status, r.late)}</td>
      </tr>`
    )
    .join("");
  document.getElementById("page-attendance").innerHTML = `
    <h1>Daily register</h1>
    <p class="sub">Gate par card tap = check-in. Doosri dafa = check-out.</p>
    <div class="toolbar">
      <label>Date <input type="date" id="att-day" value="${data.day}" /></label>
      <select id="att-class"><option value="">All classes</option>${classOptions()}</select>
      <a class="secondary" href="/api/attendance.csv?day=${data.day}" style="text-decoration:none;padding:0.6rem 0.9rem">Export CSV</a>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>Name</th><th>Roll</th><th>Class</th><th>In</th><th>Out</th><th>Status</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
  const reload = async () => {
    const qs = new URLSearchParams({ day: document.getElementById("att-day").value });
    const cid = document.getElementById("att-class").value;
    if (cid) qs.set("class_id", cid);
    renderAttendance(await api("/api/attendance?" + qs.toString()));
  };
  document.getElementById("att-day").onchange = reload;
  document.getElementById("att-class").onchange = reload;
}

async function loadReports() {
  const data = await api("/api/reports/monthly");
  const rows = data.rows
    .map(
      (r) => `<tr>
        <td>${r.name}</td>
        <td>${r.class_name}-${r.section}</td>
        <td>${r.present || 0}</td>
        <td>${r.late || 0}</td>
        <td>${r.recorded || 0}</td>
      </tr>`
    )
    .join("");
  document.getElementById("page-reports").innerHTML = `
    <h1>Monthly report</h1>
    <p class="sub">Principal / class teacher print nikal ke register ke sath laga sakte hain.</p>
    <div class="toolbar">
      <label>Month <input type="month" id="rep-month" value="${data.month}" /></label>
    </div>
    <div class="panel">
      <table>
        <thead><tr><th>Name</th><th>Class</th><th>Present days</th><th>Late</th><th>Records</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
  document.getElementById("rep-month").onchange = async (e) => {
    const next = await api("/api/reports/monthly?month=" + e.target.value);
    document.querySelector("#page-reports tbody").innerHTML = next.rows
      .map(
        (r) => `<tr><td>${r.name}</td><td>${r.class_name}-${r.section}</td><td>${r.present || 0}</td><td>${r.late || 0}</td><td>${r.recorded || 0}</td></tr>`
      )
      .join("");
  };
}

async function loadSms() {
  const data = await api("/api/sms");
  const rows = data.sms
    .map(
      (s) => `<tr>
        <td>${s.student_name || "—"}</td>
        <td>${s.phone}</td>
        <td>${s.message}</td>
        <td>${s.kind}</td>
        <td>${s.status}</td>
        <td>${clock(s.created_at)}</td>
      </tr>`
    )
    .join("");
  document.getElementById("page-sms").innerHTML = `
    <h1>Parent SMS</h1>
    <p class="sub">Demo mode mein SMS save hoti hain, paisa nahi kat-ta. Live Jazz/Telenor gateway settings se lagti hai.</p>
    <div class="panel">
      <table>
        <thead><tr><th>Student</th><th>Phone</th><th>Message</th><th>Kind</th><th>Status</th><th>Time</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

async function loadPricing() {
  document.getElementById("page-pricing").innerHTML = `
    <h1>Kitne ka becho?</h1>
    <p class="sub">Yeh numbers Pakistan 2026 bazaar rates hain. Hardware aap khareedte ho, software aap ke paas already hai.</p>
    <form id="quote-form" class="toolbar panel">
      <label>Students <input name="students" type="number" min="20" value="300" /></label>
      <label>Gates / readers <input name="gates" type="number" min="1" value="2" /></label>
      <label>School days / month <input name="school_days" type="number" min="16" value="22" /></label>
      <label><input name="print_cards" type="checkbox" checked /> Printed ID cards</label>
      <label><input name="sms_in_out" type="checkbox" checked /> In + out SMS</label>
      <button class="primary">Calculate</button>
    </form>
    <div id="quote-out"></div>
  `;
  const run = async (event) => {
    event?.preventDefault();
    const form = document.getElementById("quote-form");
    const fd = new FormData(form);
    const body = {
      students: Number(fd.get("students")),
      gates: Number(fd.get("gates")),
      school_days: Number(fd.get("school_days")),
      print_cards: fd.get("print_cards") === "on",
      sms_in_out: fd.get("sms_in_out") === "on",
    };
    const q = await api("/api/pricing/quote", { method: "POST", body: JSON.stringify(body) });
    document.getElementById("quote-out").innerHTML = `
      <div class="quote-grid">
        ${q.packages
          .map(
            (p) => `<article class="panel quote-card">
              <h3>${p.name}</h3>
              <div class="price">${money(p.price)}${p.per ? " / " + p.per : ""}</div>
              <p>${p.pitch}</p>
            </article>`
          )
          .join("")}
      </div>
      <div class="grid-2" style="margin-top:1rem">
        <div class="panel">
          <h3>Aap ki cost</h3>
          <table>
            <tr><td>Cards</td><td>${money(q.hardware.cards)}</td></tr>
            <tr><td>Card printing</td><td>${money(q.hardware.printing)}</td></tr>
            <tr><td>Readers</td><td>${money(q.hardware.readers)}</td></tr>
            <tr><td>Tablet kiosk</td><td>${money(q.hardware.tablet)}</td></tr>
            <tr><td>Install</td><td>${money(q.hardware.install)}</td></tr>
            <tr><td>SMS / month</td><td>${money(q.sms.your_cost_month)}</td></tr>
            <tr><td><strong>Year-1 kharcha</strong></td><td><strong>${money(q.your_year1_cost)}</strong></td></tr>
          </table>
        </div>
        <div class="panel">
          <h3>School se lena</h3>
          <table>
            <tr><td>Hardware sell</td><td>${money(q.hardware.sell_at)}</td></tr>
            <tr><td>Software setup</td><td>${money(q.software.setup)}</td></tr>
            <tr><td>Software / month</td><td>${money(q.software.monthly)}</td></tr>
            <tr><td>SMS sell / month</td><td>${money(q.sms.sell_month)}</td></tr>
            <tr><td><strong>Year-1 invoice</strong></td><td><strong>${money(q.year1_total_sell)}</strong></td></tr>
            <tr><td><strong>Aap ka profit</strong></td><td><strong>${money(q.profit_year1)}</strong></td></tr>
          </table>
        </div>
      </div>
      <ul class="notes">${q.notes.map((n) => `<li>${n}</li>`).join("")}</ul>
    `;
  };
  document.getElementById("quote-form").onsubmit = run;
  run();
}

async function loadSettings() {
  const data = await api("/api/settings");
  const s = data.settings;
  document.getElementById("page-settings").innerHTML = `
    <h1>School settings</h1>
    <p class="sub">Late time aur SMS yahin se control hote hain.</p>
    <form id="settings-form" class="panel" style="display:grid;gap:0.6rem;max-width:560px">
      <label>School name <input name="school_name" value="${s.school_name || ""}" /></label>
      <div class="row-2">
        <label>City <input name="school_city" value="${s.school_city || ""}" /></label>
        <label>Phone <input name="school_phone" value="${s.school_phone || ""}" /></label>
      </div>
      <div class="row-2">
        <label>Start <input name="start_time" value="${s.start_time || ""}" /></label>
        <label>Late after <input name="late_after" value="${s.late_after || ""}" /></label>
      </div>
      <label>Card debounce seconds <input name="debounce_seconds" value="${s.debounce_seconds || "90"}" /></label>
      <label>SMS provider
        <select name="sms_provider">
          <option value="demo" ${s.sms_provider === "demo" ? "selected" : ""}>Demo (no charge)</option>
          <option value="live" ${s.sms_provider === "live" ? "selected" : ""}>Live gateway</option>
        </select>
      </label>
      <label><input type="checkbox" name="sms_on_in" ${s.sms_on_in === "1" ? "checked" : ""} /> SMS on check-in</label>
      <label><input type="checkbox" name="sms_on_out" ${s.sms_on_out === "1" ? "checked" : ""} /> SMS on check-out</label>
      <button class="primary">Save settings</button>
      <p id="settings-ok" hidden>Saved.</p>
    </form>
  `;
  document.getElementById("settings-form").onsubmit = async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const values = Object.fromEntries(fd.entries());
    values.sms_on_in = fd.get("sms_on_in") ? "1" : "0";
    values.sms_on_out = fd.get("sms_on_out") ? "1" : "0";
    const saved = await api("/api/settings", { method: "PUT", body: JSON.stringify({ values }) });
    state.settings = saved.settings;
    document.getElementById("school-name").textContent = saved.settings.school_name;
    document.getElementById("school-city").textContent = saved.settings.school_city;
    document.getElementById("settings-ok").hidden = false;
  };
}

async function boot() {
  try {
    const me = await api("/api/me");
    state.user = me.user;
    state.settings = me.settings;
    document.getElementById("school-name").textContent = me.settings.school_name || "Hazri";
    document.getElementById("school-city").textContent = me.settings.school_city || "";
    document.getElementById("whoami").textContent = `${me.user.display_name} (${me.user.role})`;
    document.getElementById("logout").onclick = async () => {
      await api("/api/logout", { method: "POST" });
      window.location.href = "/login";
    };
    document.querySelectorAll(".nav nav button").forEach((btn) => {
      btn.onclick = () => showPage(btn.dataset.page);
    });
    showPage("dashboard");
  } catch (err) {
    if (err.message !== "auth") window.location.href = "/login";
  }
}

boot();
