from __future__ import annotations

from threading import Lock

from .models import Alert, AuditEvent, Device, Job, Pool, Session, to_dict


class Store:
    def __init__(self) -> None:
        self._lock = Lock()
        self.pools: dict[str, Pool] = {}
        self.devices: dict[str, Device] = {}
        self.jobs: dict[str, Job] = {}
        self.sessions: dict[str, Session] = {}
        self.audit: list[AuditEvent] = []
        self.operator = "lab"

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "pools": [to_dict(p) for p in self.pools.values()],
                "devices": [to_dict(d) for d in self.devices.values()],
                "jobs": [to_dict(j) for j in self.jobs.values()],
                "sessions": [to_dict(s) for s in self.sessions.values()],
                "audit": [to_dict(e) for e in self.audit[-80:]],
            }

    def add_pool(self, pool: Pool) -> None:
        with self._lock:
            self.pools[pool.id] = pool

    def add_device(self, device: Device) -> None:
        with self._lock:
            self.devices[device.id] = device

    def upsert_device(self, device: Device) -> None:
        with self._lock:
            existing = next((d for d in self.devices.values() if d.serial == device.serial), None)
            if existing:
                existing.name = device.name
                existing.model = device.model
                existing.os_version = device.os_version
                existing.api_level = device.api_level
                existing.status = device.status if existing.status != "maintenance" else existing.status
                existing.last_seen = device.last_seen
                existing.source = device.source
                existing.automatable = device.automatable
                return
            self.devices[device.id] = device

    def get_device(self, device_id: str) -> Device | None:
        with self._lock:
            return self.devices.get(device_id)

    def list_devices(self) -> list[Device]:
        with self._lock:
            return list(self.devices.values())

    def add_job(self, job: Job) -> None:
        with self._lock:
            self.jobs[job.id] = job

    def get_job(self, job_id: str) -> Job | None:
        with self._lock:
            return self.jobs.get(job_id)

    def list_jobs(self) -> list[Job]:
        with self._lock:
            return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)

    def add_session(self, session: Session) -> None:
        with self._lock:
            self.sessions[session.id] = session

    def get_session(self, session_id: str) -> Session | None:
        with self._lock:
            return self.sessions.get(session_id)

    def list_sessions(self) -> list[Session]:
        with self._lock:
            return sorted(self.sessions.values(), key=lambda s: s.started_at, reverse=True)

    def add_audit(self, event: AuditEvent) -> None:
        with self._lock:
            self.audit.append(event)

    def list_audit(self) -> list[AuditEvent]:
        with self._lock:
            return list(reversed(self.audit[-120:]))

    def overview(self) -> dict:
        devices = self.list_devices()
        jobs = self.list_jobs()
        sessions = [s for s in self.list_sessions() if s.status == "active"]
        by_status: dict[str, int] = {}
        for device in devices:
            by_status[device.status] = by_status.get(device.status, 0) + 1
        running = [j for j in jobs if j.status == "running"]
        queued = [j for j in jobs if j.status == "queued"]
        recent = jobs[:8]
        return {
            "device_count": len(devices),
            "online": by_status.get("online", 0),
            "busy": by_status.get("busy", 0),
            "reserved": by_status.get("reserved", 0),
            "offline": by_status.get("offline", 0) + by_status.get("maintenance", 0),
            "by_status": by_status,
            "active_sessions": len(sessions),
            "running_jobs": len(running),
            "queued_jobs": len(queued),
            "recent_jobs": [to_dict(j) for j in recent],
            "alerts": [to_dict(a) for a in self.alerts()],
        }

    def alerts(self) -> list[Alert]:
        alerts: list[Alert] = []
        for device in self.list_devices():
            if device.status == "offline":
                alerts.append(
                    Alert(
                        id=f"offline-{device.id}",
                        severity="warn",
                        device_id=device.id,
                        title=f"{device.name} is offline",
                        detail="No heartbeat. Plug it in or check USB debugging.",
                        at=device.last_seen,
                    )
                )
            if device.battery < 15 and not device.charging:
                alerts.append(
                    Alert(
                        id=f"battery-{device.id}",
                        severity="warn",
                        device_id=device.id,
                        title=f"{device.name} battery {device.battery}%",
                        detail="Automated jobs skip devices below 15% unless charging.",
                        at=device.last_seen,
                    )
                )
            if device.temperature_c >= 40:
                alerts.append(
                    Alert(
                        id=f"temp-{device.id}",
                        severity="crit" if device.temperature_c >= 42 else "warn",
                        device_id=device.id,
                        title=f"{device.name} is {device.temperature_c:.1f}°C",
                        detail="Jobs wait until the handset cools below 42°C.",
                        at=device.last_seen,
                    )
                )
            if device.storage_free_gb < 2:
                alerts.append(
                    Alert(
                        id=f"storage-{device.id}",
                        severity="warn",
                        device_id=device.id,
                        title=f"{device.name} has {device.storage_free_gb:.1f} GB free",
                        detail="Installs may fail. Clear app-under-test artifacts.",
                        at=device.last_seen,
                    )
                )
        return alerts
