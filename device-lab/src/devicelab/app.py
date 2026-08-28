from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .adb import adb_available, refresh_adb
from .lab import Lab, new_id
from .models import AUTOMATED_SUITES, AuditEvent, iso, to_dict
from .seed import seed

WEB_DIR = Path(__file__).parent / "web"


class JobIn(BaseModel):
    name: str = ""
    suite: str
    app_label: str = Field(..., min_length=1)
    pool_id: str | None = None
    device_ids: list[str] | None = None
    notes: str = ""


class SessionIn(BaseModel):
    device_id: str
    purpose: str = "manual QA"
    minutes: int = 45


class MaintenanceIn(BaseModel):
    enabled: bool = True


class Hub:
    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.clients.add(ws)

    def drop(self, ws: WebSocket) -> None:
        self.clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self.clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.drop(ws)


def operator_name(x_operator: str | None) -> str:
    name = (x_operator or "").strip()
    return name[:40] or "lab"


def create_app(lab: Lab | None = None, *, enable_scheduler: bool = True, seed_demo: bool = True) -> FastAPI:
    lab = lab or Lab()
    if seed_demo and not lab.store.devices:
        seed(lab.store)
    hub = Hub()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        stop = asyncio.Event()

        async def loop() -> None:
            while not stop.is_set():
                lab.tick()
                await hub.broadcast({"type": "tick", "overview": lab.store.overview()})
                try:
                    await asyncio.wait_for(stop.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

        task = asyncio.create_task(loop()) if enable_scheduler else None
        yield
        stop.set()
        if task:
            await task

    app = FastAPI(
        title="Bench QA Device Lab",
        version="1.0.0",
        description="Run automated and manual tests on Android devices you own.",
        lifespan=lifespan,
    )
    app.state.lab = lab

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "adb": adb_available(),
            "product": "bench",
            "purpose": "qa-device-lab",
        }

    @app.get("/api/overview")
    def overview() -> dict:
        data = lab.store.overview()
        data["adb"] = adb_available()
        data["suites"] = list(AUTOMATED_SUITES)
        return data

    @app.get("/api/pools")
    def pools() -> dict:
        return {"pools": [to_dict(p) for p in lab.store.pools.values()]}

    @app.get("/api/devices")
    def devices() -> dict:
        return {"devices": [to_dict(d) for d in lab.store.list_devices()]}

    @app.get("/api/devices/{device_id}")
    def device(device_id: str) -> dict:
        found = lab.store.get_device(device_id)
        if not found:
            raise HTTPException(404, "Device not found")
        jobs = [
            to_dict(job)
            for job in lab.store.list_jobs()
            if device_id in job.device_ids
        ][:12]
        return {"device": to_dict(found), "jobs": jobs}

    @app.post("/api/devices/{device_id}/maintenance")
    def maintenance(
        device_id: str,
        body: MaintenanceIn,
        x_operator: str | None = Header(default=None),
    ) -> dict:
        try:
            device = lab.set_maintenance(device_id, body.enabled, operator_name(x_operator))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"device": to_dict(device)}

    @app.post("/api/sessions")
    def start_session(body: SessionIn, x_operator: str | None = Header(default=None)) -> dict:
        try:
            session = lab.start_session(body.device_id, operator_name(x_operator), body.purpose, body.minutes)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"session": to_dict(session)}

    @app.post("/api/sessions/{session_id}/end")
    def end_session(session_id: str, x_operator: str | None = Header(default=None)) -> dict:
        try:
            session = lab.end_session(session_id, operator_name(x_operator))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"session": to_dict(session)}

    @app.get("/api/sessions")
    def sessions() -> dict:
        return {"sessions": [to_dict(s) for s in lab.store.list_sessions()]}

    @app.get("/api/jobs")
    def jobs() -> dict:
        return {"jobs": [to_dict(j) for j in lab.store.list_jobs()]}

    @app.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict:
        found = lab.store.get_job(job_id)
        if not found:
            raise HTTPException(404, "Job not found")
        return {"job": to_dict(found)}

    @app.post("/api/jobs")
    def create_job(body: JobIn, x_operator: str | None = Header(default=None)) -> dict:
        try:
            created = lab.create_job(
                name=body.name,
                suite=body.suite,
                app_label=body.app_label,
                pool_id=body.pool_id,
                device_ids=body.device_ids,
                created_by=operator_name(x_operator),
                notes=body.notes,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"job": to_dict(created)}

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, x_operator: str | None = Header(default=None)) -> dict:
        try:
            found = lab.cancel_job(job_id, operator_name(x_operator))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return {"job": to_dict(found)}

    @app.post("/api/sync-adb")
    def sync_adb(x_operator: str | None = Header(default=None)) -> dict:
        serials = refresh_adb(lab.store)
        lab.store.add_audit(
            AuditEvent(
                id=new_id("aud"),
                at=iso(),
                actor=operator_name(x_operator),
                action="sync_adb",
                target="rack",
                detail=f"{len(serials)} USB device(s)",
            )
        )
        return {"serials": serials, "adb": adb_available()}

    @app.get("/api/audit")
    def audit() -> dict:
        return {"events": [to_dict(e) for e in lab.store.list_audit()]}

    @app.get("/api/use")
    def acceptable_use() -> dict:
        return {
            "allowed": [
                "Phones and tablets your team owns or leases",
                "Apps you develop or have permission to test",
                "UI, smoke, regression, visual, accessibility, and instrumentation suites",
                "Manual bug reproduction with a timed reservation",
            ],
            "not_this_product": [
                "Creating or warming social / messaging accounts",
                "Fake engagement, spam, or ads fraud",
                "Identity, IMEI, or fingerprint spoofing",
                "Anything that violates a platform's terms or the law",
            ],
        }

    @app.websocket("/api/ws")
    async def ws(socket: WebSocket) -> None:
        await hub.connect(socket)
        try:
            await socket.send_json({"type": "hello", "overview": lab.store.overview()})
            while True:
                await socket.receive_text()
        except WebSocketDisconnect:
            hub.drop(socket)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
    return app


app = create_app()
