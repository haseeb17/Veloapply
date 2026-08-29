from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server import app, configure  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    configure(tmp_path / "hazri.db")
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, username="admin", password="hazri123"):
    res = client.post("/api/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res


def test_health(client):
    assert client.get("/api/health").json()["ok"] is True


def test_login_and_dashboard(client):
    login(client)
    dash = client.get("/api/dashboard").json()
    assert dash["totals"]["students"] >= 20
    assert "present" in dash["totals"]


def test_bad_login(client):
    res = client.post("/api/login", json={"username": "admin", "password": "nope"})
    assert res.status_code == 401


def test_unknown_card(client):
    login(client)
    res = client.post("/api/scan", json={"uid": "NO-SUCH-CARD"})
    assert res.status_code == 200
    assert res.json()["status"] == "unknown"


def test_check_in_then_duplicate_then_checkout(client):
    login(client)
    first = client.post("/api/scan", json={"uid": "HAZRI-1701"}).json()
    assert first["ok"] is True
    assert first["status"] in {"ok", "late", "out", "duplicate"}

    dup = client.post("/api/scan", json={"uid": "HAZRI-1701"}).json()
    assert dup["status"] == "duplicate"

    other = client.post("/api/scan", json={"uid": "HAZRI-1702"}).json()
    assert other["ok"] is True


def test_add_student_and_scan(client):
    login(client)
    classes = client.get("/api/classes").json()["classes"]
    cid = classes[0]["id"]
    created = client.post(
        "/api/students",
        json={
            "name": "Test Child",
            "roll_no": "T-99",
            "class_id": cid,
            "rfid_uid": "HAZRI-9999",
            "parent_name": "Test Parent",
            "parent_phone": "0300-0000000",
            "gender": "other",
            "active": True,
        },
    )
    assert created.status_code == 200, created.text
    scan = client.post("/api/scan", json={"uid": "hazri-9999"}).json()
    assert scan["ok"] is True
    assert scan["student"]["name"] == "Test Child"
    att = client.get("/api/attendance").json()
    row = next(r for r in att["rows"] if r["rfid_uid"] == "HAZRI-9999")
    assert row["status"] == "present"
    sms = client.get("/api/sms").json()["sms"]
    assert any("Test Child" in (s["message"] or "") for s in sms)


def test_quote_profit_positive(client):
    login(client)
    quote = client.post(
        "/api/pricing/quote",
        json={"students": 300, "gates": 2, "print_cards": True, "sms_in_out": True, "school_days": 22},
    ).json()
    assert quote["year1_total_sell"] > quote["your_year1_cost"]
    assert quote["packages"][0]["price"] > 100000


def test_kiosk_user_can_scan_not_add_student(client):
    login(client, "gate", "gate123")
    scan = client.post("/api/scan", json={"uid": "HAZRI-1001"})
    assert scan.status_code == 200
    denied = client.post(
        "/api/students",
        json={
            "name": "Nope",
            "roll_no": "X-1",
            "class_id": 1,
            "rfid_uid": "NOPE",
        },
    )
    assert denied.status_code == 403
