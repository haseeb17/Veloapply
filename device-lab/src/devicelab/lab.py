from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .models import (
    AUTOMATED_SUITES,
    SUITE_STEPS,
    AuditEvent,
    Device,
    DeviceRun,
    Job,
    Session,
    StepResult,
    iso,
    utcnow,
)
from .store import Store


FAILURES = [
    "ANR while rotating to landscape",
    "Activity did not idle within 8s after cold launch",
    "Instrumentation test timed out in SettingsFragment",
    "Visual baseline drifted 4.8% on the home screen",
]


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class Lab:
    def __init__(self, store: Store | None = None) -> None:
        self.store = store or Store()
        self.rng = random.Random(7)

    def create_job(
        self,
        *,
        name: str,
        suite: str,
        app_label: str,
        pool_id: str | None,
        device_ids: list[str] | None,
        created_by: str,
        notes: str = "",
    ) -> Job:
        if suite not in AUTOMATED_SUITES:
            raise ValueError(f"Unknown suite '{suite}'. Allowed: {', '.join(AUTOMATED_SUITES)}")
        if not app_label.strip():
            raise ValueError("app_label is required — the package or APK you own and are testing.")
        targets = self._resolve_targets(pool_id, device_ids)
        if not targets:
            raise ValueError("No automatable devices matched that pool or selection.")
        job = Job(
            id=new_id("job"),
            name=name.strip() or f"{suite} run",
            suite=suite,
            app_label=app_label.strip(),
            pool_id=pool_id,
            device_ids=[d.id for d in targets],
            status="queued",
            created_at=iso(),
            created_by=created_by,
            notes=notes,
            runs=[DeviceRun(device_id=d.id, status="queued") for d in targets],
        )
        self.store.add_job(job)
        self.store.add_audit(
            AuditEvent(
                id=new_id("aud"),
                at=iso(),
                actor=created_by,
                action="enqueue_job",
                target=job.id,
                detail=f"{suite} on {len(targets)} device(s) for {app_label}",
            )
        )
        return job

    def _resolve_targets(self, pool_id: str | None, device_ids: list[str] | None) -> list[Device]:
        devices = self.store.list_devices()
        if device_ids:
            selected = [d for d in devices if d.id in set(device_ids)]
        elif pool_id:
            selected = [d for d in devices if d.pool_id == pool_id]
        else:
            selected = [d for d in devices if d.pool_id == "pool-smoke"]
        runnable = [d for d in selected if d.automatable and d.status != "offline" and d.status != "maintenance"]
        missing = [d.id for d in selected if not d.automatable]
        if device_ids and missing and not runnable:
            raise ValueError("Selected devices are manual-only (for example iOS). Reserve them for a desk session instead.")
        return runnable

    def start_session(self, device_id: str, operator: str, purpose: str, minutes: int = 45) -> Session:
        device = self.store.get_device(device_id)
        if not device:
            raise ValueError("Unknown device")
        if device.status in {"offline", "maintenance"}:
            raise ValueError("Device is not available")
        if device.status == "busy":
            raise ValueError("Device is running an automated job")
        if device.reserved_by and device.reserved_by != operator:
            raise ValueError(f"Already reserved by {device.reserved_by}")
        until = utcnow() + timedelta(minutes=max(10, minutes))
        device.status = "reserved"
        device.reserved_by = operator
        device.reserved_until = iso(until)
        session = Session(
            id=new_id("ses"),
            device_id=device.id,
            operator=operator,
            purpose=purpose.strip() or "manual QA",
            started_at=iso(),
        )
        self.store.add_session(session)
        self.store.add_audit(
            AuditEvent(
                id=new_id("aud"),
                at=iso(),
                actor=operator,
                action="reserve",
                target=device.id,
                detail=purpose or "manual QA",
            )
        )
        return session

    def end_session(self, session_id: str, operator: str) -> Session:
        session = self.store.get_session(session_id)
        if not session or session.status != "active":
            raise ValueError("No active session")
        session.status = "ended"
        session.ended_at = iso()
        device = self.store.get_device(session.device_id)
        if device:
            device.reserved_by = None
            device.reserved_until = None
            if device.status == "reserved":
                device.status = "online"
        self.store.add_audit(
            AuditEvent(
                id=new_id("aud"),
                at=iso(),
                actor=operator,
                action="release",
                target=session.device_id,
                detail=session.id,
            )
        )
        return session

    def set_maintenance(self, device_id: str, enabled: bool, operator: str) -> Device:
        device = self.store.get_device(device_id)
        if not device:
            raise ValueError("Unknown device")
        device.status = "maintenance" if enabled else "online"
        if not enabled:
            device.last_seen = iso()
        self.store.add_audit(
            AuditEvent(
                id=new_id("aud"),
                at=iso(),
                actor=operator,
                action="maintenance" if enabled else "restore",
                target=device.id,
                detail="",
            )
        )
        return device

    def cancel_job(self, job_id: str, operator: str) -> Job:
        job = self.store.get_job(job_id)
        if not job:
            raise ValueError("Unknown job")
        if job.status in {"passed", "failed", "cancelled"}:
            return job
        job.status = "cancelled"
        job.finished_at = iso()
        for run in job.runs:
            if run.status in {"queued", "running"}:
                run.status = "cancelled"
                run.finished_at = iso()
                device = self.store.get_device(run.device_id)
                if device and device.status == "busy":
                    device.status = "online"
        self.store.add_audit(
            AuditEvent(
                id=new_id("aud"),
                at=iso(),
                actor=operator,
                action="cancel_job",
                target=job.id,
                detail="",
            )
        )
        return job

    def tick(self, now: datetime | None = None) -> None:
        now = now or utcnow()
        self._expire_reservations(now)
        self._assign_jobs(now)
        self._progress_jobs(now)
        self._drift_simulator(now)

    def _expire_reservations(self, now: datetime) -> None:
        for session in self.store.list_sessions():
            if session.status != "active":
                continue
            device = self.store.get_device(session.device_id)
            if not device or not device.reserved_until:
                continue
            until = parse_iso(device.reserved_until)
            if until and until.tzinfo is None:
                until = until.replace(tzinfo=timezone.utc)
            if until and until < now:
                session.status = "ended"
                session.ended_at = iso(now)
                device.reserved_by = None
                device.reserved_until = None
                if device.status == "reserved":
                    device.status = "online"

    def _assign_jobs(self, now: datetime) -> None:
        for job in self.store.list_jobs():
            if job.status != "queued":
                continue
            assigned = 0
            waiting = 0
            for run in job.runs:
                if run.status != "queued":
                    continue
                device = self.store.get_device(run.device_id)
                if not device:
                    run.status = "failed"
                    run.failure = "Device disappeared from the rack"
                    continue
                if device.available_for_jobs():
                    device.status = "busy"
                    run.status = "running"
                    run.started_at = iso(now)
                    assigned += 1
                else:
                    waiting += 1
            if assigned:
                job.status = "running"
                job.started_at = job.started_at or iso(now)
            elif waiting == 0 and all(r.status in {"failed", "cancelled"} for r in job.runs):
                job.status = "failed"
                job.finished_at = iso(now)

    def _progress_jobs(self, now: datetime) -> None:
        for job in self.store.list_jobs():
            if job.status != "running":
                continue
            for run in job.runs:
                if run.status != "running" or not run.started_at:
                    continue
                started = parse_iso(run.started_at) or now
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                elapsed_ms = int((now - started).total_seconds() * 1000)
                steps = SUITE_STEPS[job.suite]
                needed = 1800 + 900 * len(steps)
                if elapsed_ms < needed:
                    filled = min(len(steps), max(1, elapsed_ms // 900))
                    run.steps = [
                        StepResult(name=steps[i], status="passed", duration_ms=720 + i * 40)
                        for i in range(filled)
                    ]
                    continue
                self._finish_run(job, run, now)

            statuses = {r.status for r in job.runs}
            if statuses <= {"passed"}:
                job.status = "passed"
                job.finished_at = iso(now)
            elif statuses <= {"passed", "failed"} and "queued" not in statuses and "running" not in statuses:
                job.status = "failed" if any(r.status == "failed" for r in job.runs) else "passed"
                if any(r.status == "passed" for r in job.runs) and any(r.status == "failed" for r in job.runs):
                    job.status = "failed"
                job.finished_at = iso(now)
            elif statuses <= {"cancelled"}:
                job.status = "cancelled"
                job.finished_at = iso(now)

    def _finish_run(self, job: Job, run: DeviceRun, now: datetime) -> None:
        device = self.store.get_device(run.device_id)
        steps = SUITE_STEPS[job.suite]
        fail = self.rng.random() < 0.16
        results: list[StepResult] = []
        failure = None
        for index, name in enumerate(steps):
            if fail and index == len(steps) - 2:
                failure = self.rng.choice(FAILURES)
                results.append(StepResult(name=name, status="failed", duration_ms=1100, detail=failure))
                for remaining in steps[index + 1 :]:
                    results.append(StepResult(name=remaining, status="skipped", duration_ms=0))
                break
            results.append(StepResult(name=name, status="passed", duration_ms=680 + index * 35))
        run.steps = results
        run.status = "failed" if failure else "passed"
        run.failure = failure
        run.finished_at = iso(now)
        started = parse_iso(run.started_at) or now
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        run.duration_ms = max(0, int((now - started).total_seconds() * 1000))
        run.visual_match = None if failure else round(96.4 + self.rng.random() * 3.2, 1)
        run.screenshots = [
            {"name": "launch", "caption": "Cold start"},
            {"name": "home", "caption": "Primary screen"},
        ]
        run.log_excerpt = (
            f"I {job.suite}: targeting {job.app_label}\n"
            f"I device {run.device_id} serial={device.serial if device else '?'}\n"
            + ("E " + failure + "\n" if failure else "I instrumentation finished\n")
        )
        if device and device.status == "busy":
            device.status = "online"
            device.battery = max(8, device.battery - self.rng.randint(1, 4))
            device.last_seen = iso(now)

    def _drift_simulator(self, now: datetime) -> None:
        for device in self.store.list_devices():
            if device.source != "simulator":
                continue
            if device.charging and device.battery < 100:
                device.battery = min(100, device.battery + 1)
            if device.temperature_c > 33 and device.status != "busy":
                device.temperature_c = round(max(30.0, device.temperature_c - 0.2), 1)
            if device.status != "offline":
                device.last_seen = iso(now)
