from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from devicelab.app import create_app
from devicelab.lab import Lab
from devicelab.seed import seed


def client_and_lab():
    lab = Lab()
    seed(lab.store)
    app = create_app(lab, enable_scheduler=False, seed_demo=False)
    return TestClient(app), lab


def test_health_and_use():
    client, _ = client_and_lab()
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["purpose"] == "qa-device-lab"
    use = client.get("/api/use").json()
    assert any("own" in item.lower() for item in use["allowed"])
    assert any("social" in item.lower() for item in use["not_this_product"])


def test_overview_counts_seeded_rack():
    client, _ = client_and_lab()
    data = client.get("/api/overview").json()
    assert data["device_count"] == 14
    assert data["busy"] >= 1
    assert data["reserved"] >= 1
    assert "smoke" in data["suites"]


def test_dashboard_served():
    client, _ = client_and_lab()
    page = client.get("/")
    assert page.status_code == 200
    assert "QA device lab" in page.text


def test_rejects_unknown_suite_and_blank_app():
    client, _ = client_and_lab()
    bad_suite = client.post(
        "/api/jobs",
        json={"suite": "whatsapp_warmup", "app_label": "com.example.app"},
    )
    assert bad_suite.status_code == 400
    blank = client.post("/api/jobs", json={"suite": "smoke", "app_label": ""})
    assert blank.status_code == 422


def test_ios_only_selection_is_rejected():
    client, _ = client_and_lab()
    res = client.post(
        "/api/jobs",
        json={"suite": "smoke", "app_label": "com.example.app", "device_ids": ["iph15"]},
    )
    assert res.status_code == 400
    assert "manual-only" in res.json()["detail"]


def test_queue_smoke_and_complete_on_tick():
    client, lab = client_and_lab()
    created = client.post(
        "/api/jobs",
        headers={"X-Operator": "ci"},
        json={
            "name": "PR smoke",
            "suite": "install_launch",
            "app_label": "com.example.shop",
            "device_ids": ["px8p"],
        },
    )
    assert created.status_code == 200
    job_id = created.json()["job"]["id"]
    assert created.json()["job"]["status"] == "queued"

    t0 = datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc)
    lab.tick(t0)
    running = client.get(f"/api/jobs/{job_id}").json()["job"]
    assert running["status"] == "running"
    assert lab.store.get_device("px8p").status == "busy"

    lab.tick(t0 + timedelta(seconds=20))
    done = client.get(f"/api/jobs/{job_id}").json()["job"]
    assert done["status"] in {"passed", "failed"}
    assert lab.store.get_device("px8p").status == "online"
    assert done["runs"][0]["steps"]


def test_low_battery_waits():
    _, lab = client_and_lab()
    job = lab.create_job(
        name="wait",
        suite="smoke",
        app_label="com.example.app",
        pool_id=None,
        device_ids=["a54"],
        created_by="qa",
    )
    lab.tick(datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc))
    assert job.runs[0].status == "queued"
    assert lab.store.get_device("a54").status == "online"


def test_reserve_and_release():
    client, lab = client_and_lab()
    started = client.post(
        "/api/sessions",
        headers={"X-Operator": "hasan"},
        json={"device_id": "flip5", "purpose": "Repro landscape crash", "minutes": 20},
    )
    assert started.status_code == 200
    assert lab.store.get_device("flip5").status == "reserved"
    session_id = started.json()["session"]["id"]
    ended = client.post(f"/api/sessions/{session_id}/end", headers={"X-Operator": "hasan"})
    assert ended.status_code == 200
    assert lab.store.get_device("flip5").status == "online"


def test_cannot_reserve_busy_device():
    client, _ = client_and_lab()
    res = client.post("/api/sessions", json={"device_id": "s24", "purpose": "nope"})
    assert res.status_code == 409


def test_cancel_job_frees_device():
    client, lab = client_and_lab()
    created = client.post(
        "/api/jobs",
        json={"suite": "regression", "app_label": "com.example.app", "device_ids": ["px6a"]},
    )
    job_id = created.json()["job"]["id"]
    lab.tick(datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc))
    assert lab.store.get_device("px6a").status == "busy"
    client.post(f"/api/jobs/{job_id}/cancel")
    assert lab.store.get_job(job_id).status == "cancelled"
    assert lab.store.get_device("px6a").status == "online"


def test_maintenance_and_audit():
    client, lab = client_and_lab()
    res = client.post(
        "/api/devices/gpower/maintenance",
        headers={"X-Operator": "ops"},
        json={"enabled": True},
    )
    assert res.json()["device"]["status"] == "maintenance"
    events = client.get("/api/audit").json()["events"]
    assert any(e["action"] == "maintenance" and e["actor"] == "ops" for e in events)
