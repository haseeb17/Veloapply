"""Demo school data so a sales visit works without hardware."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from db import get_setting, hash_password, utcnow

ADMIN_PASSWORD = "hazri123"

STUDENTS = [
    # Playgroup
    ("Ahmed Raza", "PG-01", "Playgroup", "A", "HAZRI-1001", "Imran Raza", "0300-1112233", "male"),
    ("Hania Malik", "PG-02", "Playgroup", "A", "HAZRI-1002", "Sana Malik", "0301-4455667", "female"),
    ("Zayan Khan", "PG-03", "Playgroup", "A", "HAZRI-1003", "Bilal Khan", "0321-7788990", "male"),
    # Nursery
    ("Ayesha Siddiqui", "N-01", "Nursery", "A", "HAZRI-1101", "Farah Siddiqui", "0333-2211009", "female"),
    ("Hassan Ali", "N-02", "Nursery", "A", "HAZRI-1102", "Usman Ali", "0302-6677881", "male"),
    ("Meerab Fatima", "N-03", "Nursery", "A", "HAZRI-1103", "Nadia Fatima", "0345-9900112", "female"),
    # KG
    ("Ibrahim Sheikh", "KG-01", "KG", "A", "HAZRI-1201", "Omar Sheikh", "0312-3344556", "male"),
    ("Noor Zahra", "KG-02", "KG", "A", "HAZRI-1202", "Amina Zahra", "0308-1122334", "female"),
    ("Rayyan Ahmed", "KG-03", "KG", "A", "HAZRI-1203", "Shahid Ahmed", "0331-5566778", "male"),
    # Class 1
    ("Fatima Noor", "1-01", "1", "A", "HAZRI-1301", "Khalid Noor", "0300-9988776", "female"),
    ("Ali Haider", "1-02", "1", "A", "HAZRI-1302", "Tariq Haider", "0322-4433221", "male"),
    ("Sara Qureshi", "1-03", "1", "A", "HAZRI-1303", "Hina Qureshi", "0344-7766554", "female"),
    ("Hamza Iqbal", "1-04", "1", "B", "HAZRI-1304", "Javed Iqbal", "0315-8899001", "male"),
    ("Zara Bukhari", "1-05", "1", "B", "HAZRI-1305", "Saima Bukhari", "0307-2233445", "female"),
    # Class 2
    ("Muhammad Umar", "2-01", "2", "A", "HAZRI-1401", "Asif Umar", "0334-6677889", "male"),
    ("Abeer Shah", "2-02", "2", "A", "HAZRI-1402", "Rabia Shah", "0301-3344556", "female"),
    ("Yousuf Kamran", "2-03", "2", "A", "HAZRI-1403", "Haseeb Kamran", "0321-1212121", "male"),
    # Class 5
    ("Laiba Rehman", "5-01", "5", "A", "HAZRI-1501", "Abdul Rehman", "0300-5556677", "female"),
    ("Daniyal Farooq", "5-02", "5", "A", "HAZRI-1502", "Imtiaz Farooq", "0345-8899000", "male"),
    ("Maham Javed", "5-03", "5", "A", "HAZRI-1503", "Nida Javed", "0310-1010101", "female"),
    ("Saad Anwar", "5-04", "5", "A", "HAZRI-1504", "Faisal Anwar", "0333-4040404", "male"),
    # Class 8
    ("Areeba Hassan", "8-01", "8", "A", "HAZRI-1601", "Hassan Raza", "0302-7778889", "female"),
    ("Bilal Aslam", "8-02", "8", "A", "HAZRI-1602", "Aslam Pervaiz", "0322-1234567", "male"),
    ("Eman Tariq", "8-03", "8", "A", "HAZRI-1603", "Tariq Mehmood", "0344-7654321", "female"),
    # Matric
    ("Hafsa Nadeem", "10-01", "10", "A", "HAZRI-1701", "Nadeem Akhtar", "0308-9090909", "female"),
    ("Usman Ghani", "10-02", "10", "A", "HAZRI-1702", "Ghulam Nabi", "0316-8080808", "male"),
    ("Zainab Iftikhar", "10-03", "10", "A", "HAZRI-1703", "Iftikhar Ahmed", "0331-7070707", "female"),
]


def _class_id(db: sqlite3.Connection, name: str, section: str) -> int:
    row = db.execute(
        "SELECT id FROM classes WHERE name = ? AND section = ?",
        (name, section),
    ).fetchone()
    if row:
        return int(row["id"])
    cur = db.execute(
        "INSERT INTO classes(name, section) VALUES (?, ?)",
        (name, section),
    )
    return int(cur.lastrowid)


def seed_if_empty(db: sqlite3.Connection) -> None:
    user_count = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
    if user_count:
        return

    db.execute(
        "INSERT INTO users(username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
        ("admin", hash_password(ADMIN_PASSWORD), "School Admin", "admin"),
    )
    db.execute(
        "INSERT INTO users(username, password_hash, display_name, role) VALUES (?, ?, ?, ?)",
        ("gate", hash_password("gate123"), "Gate Kiosk", "kiosk"),
    )

    now = utcnow()
    student_ids: list[int] = []
    for name, roll, klass, section, uid, parent, phone, gender in STUDENTS:
        cid = _class_id(db, klass, section)
        cur = db.execute(
            """
            INSERT INTO students(name, roll_no, class_id, rfid_uid, parent_name, parent_phone, gender, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (name, roll, cid, uid, parent, phone, gender, now),
        )
        student_ids.append(int(cur.lastrowid))

    today = datetime.now().date()
    late_after = get_setting(db, "late_after", "08:15")
    hour, minute = [int(p) for p in late_after.split(":")]

    # Yesterday: almost everyone present so reports look real.
    yesterday = (today - timedelta(days=1)).isoformat()
    for index, sid in enumerate(student_ids):
        if index % 9 == 0:
            db.execute(
                """
                INSERT INTO attendance_days(student_id, day, check_in, check_out, status, late)
                VALUES (?, ?, NULL, NULL, 'absent', 0)
                """,
                (sid, yesterday),
            )
            continue
        check_in_dt = datetime(today.year, today.month, today.day, 7, 52, tzinfo=timezone.utc) - timedelta(days=1)
        check_in_dt = check_in_dt.replace(minute=40 + (index % 15))
        late = 1 if check_in_dt.hour > hour or (check_in_dt.hour == hour and check_in_dt.minute > minute) else 0
        check_out_dt = check_in_dt.replace(hour=14, minute=10 + (index % 20))
        db.execute(
            """
            INSERT INTO attendance_days(student_id, day, check_in, check_out, status, late)
            VALUES (?, ?, ?, ?, 'present', ?)
            """,
            (sid, yesterday, check_in_dt.isoformat(), check_out_dt.isoformat(), late),
        )

    # Today: a mix of present / late / not yet arrived.
    day = today.isoformat()
    for index, sid in enumerate(student_ids):
        if index % 7 == 0:
            continue
        minute_off = 5 + (index * 3) % 25
        check_in_dt = datetime.now(timezone.utc).replace(hour=8, minute=minute_off, second=0, microsecond=0)
        late = 1 if minute_off > 15 else 0
        db.execute(
            """
            INSERT INTO attendance_days(student_id, day, check_in, check_out, status, late)
            VALUES (?, ?, ?, NULL, 'present', ?)
            """,
            (sid, day, check_in_dt.isoformat(), late),
        )
        student = db.execute("SELECT * FROM students WHERE id = ?", (sid,)).fetchone()
        db.execute(
            """
            INSERT INTO scans(student_id, rfid_uid, event_type, status, note, created_at)
            VALUES (?, ?, 'in', ?, ?, ?)
            """,
            (
                sid,
                student["rfid_uid"],
                "late" if late else "ok",
                "Demo morning scan",
                check_in_dt.isoformat(),
            ),
        )
        if student["parent_phone"]:
            school = get_setting(db, "school_name")
            when = check_in_dt.strftime("%I:%M %p")
            msg = f"{school}: {student['name']} school pohanch gaye {when}."
            db.execute(
                """
                INSERT INTO sms_logs(student_id, phone, message, kind, status, created_at)
                VALUES (?, ?, ?, 'in', 'demo', ?)
                """,
                (sid, student["parent_phone"], msg, check_in_dt.isoformat()),
            )

    db.commit()
