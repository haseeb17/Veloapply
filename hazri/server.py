"""Hazri — school RFID / chip-card attendance server."""

from __future__ import annotations

import csv
import io
import os
import secrets
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from db import (
    all_settings,
    connect,
    get_setting,
    init_db,
    set_settings,
    utcnow,
    verify_password,
)
from seed import seed_if_empty

SESSION_COOKIE = "hazri_session"
SESSION_TTL_HOURS = 14
SESSIONS: dict[str, dict[str, Any]] = {}
db = None


def configure(path: Path | None = None) -> None:
    global db
    if db is not None:
        try:
            db.close()
        except Exception:
            pass
    db = connect(path)
    init_db(db)
    seed_if_empty(db)


configure()

app = FastAPI(title="Hazri", version="1.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=str(ROOT / "templates"))


class LoginBody(BaseModel):
    username: str
    password: str


class StudentBody(BaseModel):
    name: str
    roll_no: str
    class_id: int
    rfid_uid: str
    parent_name: str = ""
    parent_phone: str = ""
    gender: str = "other"
    active: bool = True


class ClassBody(BaseModel):
    name: str
    section: str = "A"


class ScanBody(BaseModel):
    uid: str
    source: str = "kiosk"


class SettingsBody(BaseModel):
    values: dict[str, str]


class QuoteBody(BaseModel):
    students: int = Field(ge=20, le=5000)
    gates: int = Field(ge=1, le=12)
    print_cards: bool = True
    sms_in_out: bool = True
    school_days: int = Field(default=22, ge=16, le=26)


def _now_local() -> datetime:
    # Pakistan Standard Time, UTC+5 — schools here do not run on UTC clocks.
    return datetime.now(timezone(timedelta(hours=5)))


def _today() -> str:
    return _now_local().date().isoformat()


def _parse_hhmm(value: str) -> time:
    hour, minute = [int(p) for p in value.split(":")[:2]]
    return time(hour, minute)


def _is_late(when: datetime) -> bool:
    late_after = _parse_hhmm(get_setting(db, "late_after", "08:15"))
    return when.timetz().replace(tzinfo=None) > late_after


def _current_user(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    session = SESSIONS.get(token)
    if not session:
        return None
    expires = datetime.fromisoformat(session["expires"])
    if datetime.now(timezone.utc) > expires:
        SESSIONS.pop(token, None)
        return None
    return session["user"]


def require_user(request: Request, roles: tuple[str, ...] | None = None) -> dict[str, Any]:
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    if roles and user["role"] not in roles:
        raise HTTPException(status_code=403, detail="Not allowed")
    return user


def student_row(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "roll_no": row["roll_no"],
        "class_id": row["class_id"],
        "class_name": row["class_name"],
        "section": row["section"],
        "class_label": f"{row['class_name']}-{row['section']}".rstrip("-"),
        "rfid_uid": row["rfid_uid"],
        "parent_name": row["parent_name"],
        "parent_phone": row["parent_phone"],
        "gender": row["gender"],
        "active": bool(row["active"]),
        "created_at": row["created_at"],
    }


def fetch_student(student_id: int):
    return db.execute(
        """
        SELECT s.*, c.name AS class_name, c.section AS section
        FROM students s
        JOIN classes c ON c.id = s.class_id
        WHERE s.id = ?
        """,
        (student_id,),
    ).fetchone()


def queue_sms(student, kind: str, when: datetime) -> None:
    if not student["parent_phone"]:
        return
    flag = get_setting(db, f"sms_on_{kind}", "1")
    if flag != "1":
        return
    school = get_setting(db, "school_name", "School")
    clock = when.strftime("%I:%M %p")
    if kind == "in":
        message = f"{school}: {student['name']} school pohanch gaye {clock}."
    else:
        message = f"{school}: {student['name']} school se nikle {clock}."
    provider = get_setting(db, "sms_provider", "demo")
    status = "demo" if provider == "demo" else "queued"
    db.execute(
        """
        INSERT INTO sms_logs(student_id, phone, message, kind, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (student["id"], student["parent_phone"], message, kind, status, utcnow()),
    )


def record_scan(uid: str, source: str) -> dict[str, Any]:
    uid = uid.strip().upper().replace(" ", "")
    if not uid:
        raise HTTPException(status_code=400, detail="Card UID missing")

    now = _now_local()
    student = db.execute(
        """
        SELECT s.*, c.name AS class_name, c.section AS section
        FROM students s
        JOIN classes c ON c.id = s.class_id
        WHERE upper(replace(s.rfid_uid, ' ', '')) = ? AND s.active = 1
        """,
        (uid,),
    ).fetchone()

    if not student:
        db.execute(
            """
            INSERT INTO scans(student_id, rfid_uid, event_type, status, note, created_at)
            VALUES (NULL, ?, 'unknown', 'unknown', ?, ?)
            """,
            (uid, f"Unknown card from {source}", utcnow()),
        )
        db.commit()
        return {
            "ok": False,
            "status": "unknown",
            "title": "Unknown card",
            "message": "Yeh card register nahi. Office mein student assign karein.",
            "uid": uid,
            "at": now.isoformat(),
        }

    debounce = int(get_setting(db, "debounce_seconds", "90"))
    last = db.execute(
        """
        SELECT created_at, event_type FROM scans
        WHERE student_id = ? AND status != 'unknown'
        ORDER BY id DESC LIMIT 1
        """,
        (student["id"],),
    ).fetchone()
    if last:
        last_at = datetime.fromisoformat(last["created_at"])
        if last_at.tzinfo is None:
            last_at = last_at.replace(tzinfo=timezone.utc)
        delta = (datetime.now(timezone.utc) - last_at.astimezone(timezone.utc)).total_seconds()
        if delta < debounce:
            return {
                "ok": True,
                "status": "duplicate",
                "title": student["name"],
                "message": "Card abhi scan ho chuka hai. Thora wait karein.",
                "student": student_row(student),
                "uid": uid,
                "at": now.isoformat(),
            }

    day = now.date().isoformat()
    existing = db.execute(
        "SELECT * FROM attendance_days WHERE student_id = ? AND day = ?",
        (student["id"], day),
    ).fetchone()

    if existing is None or existing["check_in"] is None:
        late = _is_late(now)
        status = "late" if late else "ok"
        event = "in"
        if existing is None:
            db.execute(
                """
                INSERT INTO attendance_days(student_id, day, check_in, check_out, status, late)
                VALUES (?, ?, ?, NULL, 'present', ?)
                """,
                (student["id"], day, now.isoformat(), 1 if late else 0),
            )
        else:
            db.execute(
                """
                UPDATE attendance_days
                SET check_in = ?, status = 'present', late = ?
                WHERE id = ?
                """,
                (now.isoformat(), 1 if late else 0, existing["id"]),
            )
        note = "Late arrival" if late else "Check-in"
        queue_sms(student, "in", now)
        title_status = "Late" if late else "Present"
        message = (
            f"Late — school {get_setting(db, 'late_after', '08:15')} ke baad."
            if late
            else "Check-in ho gaya. Wali ko SMS queue mein hai."
        )
    else:
        event = "out"
        status = "ok"
        title_status = "Check-out"
        db.execute(
            "UPDATE attendance_days SET check_out = ? WHERE id = ?",
            (now.isoformat(), existing["id"]),
        )
        queue_sms(student, "out", now)
        message = "Check-out ho gaya. Safar khair se."
        note = "Check-out"

    db.execute(
        """
        INSERT INTO scans(student_id, rfid_uid, event_type, status, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (student["id"], student["rfid_uid"], event, status, note, utcnow()),
    )
    db.commit()
    return {
        "ok": True,
        "status": status if event == "in" else "out",
        "event": event,
        "title": student["name"],
        "title_status": title_status,
        "message": message,
        "student": student_row(student),
        "uid": uid,
        "at": now.isoformat(),
    }


def compute_quote(body: QuoteBody) -> dict[str, Any]:
    """Pakistan 2026 street prices for a typical 1-campus RFID install."""
    card_unit = 90
    print_unit = 180 if body.print_cards else 0
    reader_unit = 8500
    tablet = 32000
    install = 8000 + (body.gates - 1) * 4000
    mini_pc = 0 if body.gates == 1 else 18000

    cards = body.students * card_unit
    printing = body.students * print_unit
    readers = body.gates * reader_unit
    hardware_cost = cards + printing + readers + tablet + install + mini_pc
    hardware_sell = int(round(hardware_cost * 1.28 / 1000) * 1000)

    if body.students <= 200:
        setup = 45000
        monthly = 8000
    elif body.students <= 500:
        setup = 75000
        monthly = 12000
    elif body.students <= 1000:
        setup = 120000
        monthly = 18000
    else:
        setup = 180000
        monthly = 28000

    sms_unit = 0.55
    sms_per_day = 2 if body.sms_in_out else 1
    sms_month = int(body.students * sms_per_day * body.school_days * sms_unit)
    sms_sell = int(sms_month * 1.25)

    year1_software = setup + monthly * 12
    year1_total = hardware_sell + year1_software + sms_sell * 12
    your_cost = hardware_cost + sms_month * 12  # software you already have
    profit_year1 = year1_total - your_cost

    recommended_packages = [
        {
            "name": "Setup + 3 months",
            "price": hardware_sell + setup + monthly * 3 + sms_sell * 3,
            "pitch": "School ko chhoti cheez lagti hai. Aap hardware + software lock kar lete ho.",
        },
        {
            "name": "Year-1 bundle",
            "price": year1_total,
            "pitch": "Sab se seedha quote: cards, readers, software, SMS ek saal.",
        },
        {
            "name": "Per student / year",
            "price": int((year1_software + sms_sell * 12) / body.students),
            "per": "student",
            "pitch": "Bade school ko yeh model pasand aata hai. Hardware alag se.",
        },
    ]

    return {
        "students": body.students,
        "gates": body.gates,
        "currency": "PKR",
        "hardware": {
            "cards": cards,
            "printing": printing,
            "readers": readers,
            "tablet": tablet,
            "install": install,
            "mini_pc": mini_pc,
            "your_cost": hardware_cost,
            "sell_at": hardware_sell,
            "margin": hardware_sell - hardware_cost,
        },
        "software": {
            "setup": setup,
            "monthly": monthly,
            "year": year1_software,
        },
        "sms": {
            "unit": sms_unit,
            "your_cost_month": sms_month,
            "sell_month": sms_sell,
        },
        "year1_total_sell": year1_total,
        "your_year1_cost": your_cost,
        "profit_year1": profit_year1,
        "packages": recommended_packages,
        "notes": [
            "Card rates EM4100 / Mifare Classic ke local bazaar (Lahore/Karachi Hall Road, Hafeez Center) par hain.",
            "USB reader keyboard-wedge hai — Windows laptop ya Android box par tap karte hi UID type ho jata hai.",
            "SMS Jazz/Telenor bulk gateway se. Demo mode mein SMS save hoti hain, paisa nahi kat-ta.",
            "Aap ka software cost ab almost zero hai kyun ke Hazri ready hai. Profit software + SMS margin se aati hai.",
        ],
    }


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("app.html", {"request": request})


@app.get("/kiosk", response_class=HTMLResponse)
def kiosk(request: Request):
    return templates.TemplateResponse("kiosk.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/api/health")
def health():
    return {"ok": True, "name": "Hazri"}


@app.post("/api/login")
def login(body: LoginBody, response: Response):
    row = db.execute(
        "SELECT * FROM users WHERE username = ?",
        (body.username.strip().lower(),),
    ).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Ghalat username ya password")
    token = secrets.token_urlsafe(24)
    user = {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
    }
    SESSIONS[token] = {
        "user": user,
        "expires": (datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)).isoformat(),
    }
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_TTL_HOURS * 3600,
    )
    return {"ok": True, "user": user}


@app.post("/api/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        SESSIONS.pop(token, None)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not logged in")
    return {"user": user, "settings": all_settings(db)}


@app.get("/api/dashboard")
def dashboard(request: Request, day: str | None = None):
    require_user(request)
    day = day or _today()
    total = db.execute("SELECT COUNT(*) AS n FROM students WHERE active = 1").fetchone()["n"]
    present = db.execute(
        "SELECT COUNT(*) AS n FROM attendance_days WHERE day = ? AND status = 'present'",
        (day,),
    ).fetchone()["n"]
    late = db.execute(
        "SELECT COUNT(*) AS n FROM attendance_days WHERE day = ? AND late = 1",
        (day,),
    ).fetchone()["n"]
    absent = max(total - present, 0)
    recent = db.execute(
        """
        SELECT sc.id, sc.event_type, sc.status, sc.created_at, sc.rfid_uid,
               s.name AS student_name, s.roll_no, c.name AS class_name, c.section AS section
        FROM scans sc
        LEFT JOIN students s ON s.id = sc.student_id
        LEFT JOIN classes c ON c.id = s.class_id
        ORDER BY sc.id DESC
        LIMIT 12
        """
    ).fetchall()
    by_class = db.execute(
        """
        SELECT c.id, c.name, c.section,
               COUNT(s.id) AS total,
               SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present
        FROM classes c
        LEFT JOIN students s ON s.class_id = c.id AND s.active = 1
        LEFT JOIN attendance_days a ON a.student_id = s.id AND a.day = ?
        GROUP BY c.id
        ORDER BY c.name, c.section
        """,
        (day,),
    ).fetchall()
    return {
        "day": day,
        "school": get_setting(db, "school_name"),
        "city": get_setting(db, "school_city"),
        "totals": {
            "students": total,
            "present": present,
            "late": late,
            "absent": absent,
        },
        "recent": [dict(r) for r in recent],
        "by_class": [dict(r) for r in by_class],
    }


@app.get("/api/classes")
def list_classes(request: Request):
    require_user(request)
    rows = db.execute(
        """
        SELECT c.*, COUNT(s.id) AS student_count
        FROM classes c
        LEFT JOIN students s ON s.class_id = c.id AND s.active = 1
        GROUP BY c.id
        ORDER BY c.name, c.section
        """
    ).fetchall()
    return {"classes": [dict(r) for r in rows]}


@app.post("/api/classes")
def create_class(request: Request, body: ClassBody):
    require_user(request, ("admin",))
    try:
        cur = db.execute(
            "INSERT INTO classes(name, section) VALUES (?, ?)",
            (body.name.strip(), body.section.strip() or "A"),
        )
        db.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Class pehle se maujood hai") from exc
    return {"id": cur.lastrowid}


@app.get("/api/students")
def list_students(request: Request, q: str = "", class_id: int | None = None):
    require_user(request)
    sql = """
        SELECT s.*, c.name AS class_name, c.section AS section
        FROM students s
        JOIN classes c ON c.id = s.class_id
        WHERE 1=1
    """
    params: list[Any] = []
    if q.strip():
        like = f"%{q.strip()}%"
        sql += " AND (s.name LIKE ? OR s.roll_no LIKE ? OR s.rfid_uid LIKE ? OR s.parent_phone LIKE ?)"
        params.extend([like, like, like, like])
    if class_id:
        sql += " AND s.class_id = ?"
        params.append(class_id)
    sql += " ORDER BY c.name, c.section, s.roll_no"
    rows = db.execute(sql, params).fetchall()
    return {"students": [student_row(r) for r in rows]}


@app.post("/api/students")
def create_student(request: Request, body: StudentBody):
    require_user(request, ("admin",))
    uid = body.rfid_uid.strip().upper()
    try:
        cur = db.execute(
            """
            INSERT INTO students(name, roll_no, class_id, rfid_uid, parent_name, parent_phone, gender, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                body.name.strip(),
                body.roll_no.strip(),
                body.class_id,
                uid,
                body.parent_name.strip(),
                body.parent_phone.strip(),
                body.gender,
                1 if body.active else 0,
                utcnow(),
            ),
        )
        db.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Roll no ya card UID pehle se used hai") from exc
    return {"id": cur.lastrowid, "student": student_row(fetch_student(int(cur.lastrowid)))}


@app.put("/api/students/{student_id}")
def update_student(request: Request, student_id: int, body: StudentBody):
    require_user(request, ("admin",))
    if not fetch_student(student_id):
        raise HTTPException(status_code=404, detail="Student nahi mila")
    try:
        db.execute(
            """
            UPDATE students
            SET name=?, roll_no=?, class_id=?, rfid_uid=?, parent_name=?, parent_phone=?, gender=?, active=?
            WHERE id=?
            """,
            (
                body.name.strip(),
                body.roll_no.strip(),
                body.class_id,
                body.rfid_uid.strip().upper(),
                body.parent_name.strip(),
                body.parent_phone.strip(),
                body.gender,
                1 if body.active else 0,
                student_id,
            ),
        )
        db.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Update fail — UID/roll duplicate ho sakta hai") from exc
    return {"student": student_row(fetch_student(student_id))}


@app.delete("/api/students/{student_id}")
def delete_student(request: Request, student_id: int):
    require_user(request, ("admin",))
    db.execute("UPDATE students SET active = 0 WHERE id = ?", (student_id,))
    db.commit()
    return {"ok": True}


@app.post("/api/scan")
def scan(request: Request, body: ScanBody):
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Login required")
    return record_scan(body.uid, body.source)


@app.get("/api/attendance")
def attendance(request: Request, day: str | None = None, class_id: int | None = None):
    require_user(request)
    day = day or _today()
    sql = """
        SELECT s.id, s.name, s.roll_no, s.rfid_uid, s.parent_phone,
               c.name AS class_name, c.section AS section,
               a.check_in, a.check_out, a.status, a.late
        FROM students s
        JOIN classes c ON c.id = s.class_id
        LEFT JOIN attendance_days a ON a.student_id = s.id AND a.day = ?
        WHERE s.active = 1
    """
    params: list[Any] = [day]
    if class_id:
        sql += " AND s.class_id = ?"
        params.append(class_id)
    sql += " ORDER BY c.name, c.section, s.roll_no"
    rows = []
    for row in db.execute(sql, params).fetchall():
        item = dict(row)
        item["status"] = item["status"] or "absent"
        item["late"] = bool(item["late"])
        rows.append(item)
    return {"day": day, "rows": rows}


@app.get("/api/reports/monthly")
def monthly(request: Request, month: str | None = None):
    require_user(request)
    month = month or _now_local().strftime("%Y-%m")
    rows = db.execute(
        """
        SELECT s.id, s.name, s.roll_no, c.name AS class_name, c.section AS section,
               COUNT(a.id) AS recorded,
               SUM(CASE WHEN a.status = 'present' THEN 1 ELSE 0 END) AS present,
               SUM(a.late) AS late
        FROM students s
        JOIN classes c ON c.id = s.class_id
        LEFT JOIN attendance_days a ON a.student_id = s.id AND substr(a.day, 1, 7) = ?
        WHERE s.active = 1
        GROUP BY s.id
        ORDER BY c.name, s.roll_no
        """,
        (month,),
    ).fetchall()
    return {"month": month, "rows": [dict(r) for r in rows]}


@app.get("/api/attendance.csv")
def attendance_csv(request: Request, day: str | None = None):
    require_user(request)
    day = day or _today()
    payload = attendance(request, day)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Name", "Roll", "Class", "Card", "Check-in", "Check-out", "Status", "Late", "Parent"])
    for row in payload["rows"]:
        writer.writerow(
            [
                day,
                row["name"],
                row["roll_no"],
                f"{row['class_name']}-{row['section']}",
                row["rfid_uid"],
                row["check_in"] or "",
                row["check_out"] or "",
                row["status"],
                "yes" if row["late"] else "no",
                row["parent_phone"],
            ]
        )
    buf.seek(0)
    filename = f"hazri-attendance-{day}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/scans")
def scans(request: Request, limit: int = 40):
    require_user(request)
    rows = db.execute(
        """
        SELECT sc.*, s.name AS student_name, c.name AS class_name, c.section AS section
        FROM scans sc
        LEFT JOIN students s ON s.id = sc.student_id
        LEFT JOIN classes c ON c.id = s.class_id
        ORDER BY sc.id DESC
        LIMIT ?
        """,
        (min(limit, 200),),
    ).fetchall()
    return {"scans": [dict(r) for r in rows]}


@app.get("/api/sms")
def sms(request: Request, limit: int = 50):
    require_user(request)
    rows = db.execute(
        """
        SELECT sm.*, s.name AS student_name
        FROM sms_logs sm
        LEFT JOIN students s ON s.id = sm.student_id
        ORDER BY sm.id DESC
        LIMIT ?
        """,
        (min(limit, 200),),
    ).fetchall()
    return {"sms": [dict(r) for r in rows]}


@app.get("/api/settings")
def read_settings(request: Request):
    require_user(request, ("admin",))
    return {"settings": all_settings(db)}


@app.put("/api/settings")
def write_settings(request: Request, body: SettingsBody):
    require_user(request, ("admin",))
    allowed = {
        "school_name",
        "school_city",
        "school_phone",
        "start_time",
        "end_time",
        "late_after",
        "debounce_seconds",
        "sms_on_in",
        "sms_on_out",
        "sms_provider",
    }
    values = {k: v for k, v in body.values.items() if k in allowed}
    set_settings(db, values)
    return {"settings": all_settings(db)}


@app.post("/api/pricing/quote")
def quote(request: Request, body: QuoteBody):
    require_user(request)
    return compute_quote(body)


@app.get("/api/demo-cards")
def demo_cards(request: Request):
    require_user(request)
    rows = db.execute(
        """
        SELECT s.name, s.rfid_uid, s.roll_no, c.name AS class_name, c.section AS section
        FROM students s
        JOIN classes c ON c.id = s.class_id
        WHERE s.active = 1
        ORDER BY s.id
        LIMIT 12
        """
    ).fetchall()
    return {"cards": [dict(r) for r in rows]}




if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8787"))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
