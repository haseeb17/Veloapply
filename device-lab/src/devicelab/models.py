from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Iterable


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(ts: datetime | None = None) -> str:
    return (ts or utcnow()).isoformat(timespec="seconds")


def to_dict(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: to_dict(val) for key, val in asdict(value).items()}
    if isinstance(value, dict):
        return {key: to_dict(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_dict(item) for item in value]
    return value


AUTOMATED_SUITES = (
    "install_launch",
    "smoke",
    "regression",
    "visual_diff",
    "accessibility",
    "instrumentation",
)

SUITE_STEPS: dict[str, list[str]] = {
    "install_launch": [
        "verify_device_health",
        "install_app_under_test",
        "cold_launch",
        "wait_for_idle",
        "capture_launch_screenshot",
    ],
    "smoke": [
        "verify_device_health",
        "install_app_under_test",
        "cold_launch",
        "open_primary_screen",
        "rotate_portrait_landscape",
        "background_and_resume",
        "capture_screenshots",
    ],
    "regression": [
        "verify_device_health",
        "install_app_under_test",
        "cold_launch",
        "exercise_core_flows",
        "rotate_and_resize",
        "low_memory_trim",
        "capture_screenshots",
        "collect_logcat",
    ],
    "visual_diff": [
        "verify_device_health",
        "install_app_under_test",
        "open_baseline_screens",
        "capture_pixel_buffers",
        "compare_against_baseline",
    ],
    "accessibility": [
        "verify_device_health",
        "install_app_under_test",
        "enable_talkback_probe",
        "scan_content_descriptions",
        "check_contrast_and_touch_targets",
        "capture_screenshots",
    ],
    "instrumentation": [
        "verify_device_health",
        "install_app_under_test",
        "install_test_apk",
        "run_android_instrumentation",
        "parse_am_instrument_output",
        "collect_logcat",
    ],
}


@dataclass
class Pool:
    id: str
    name: str
    purpose: str
    color: str


@dataclass
class Device:
    id: str
    serial: str
    name: str
    manufacturer: str
    model: str
    form_factor: str
    os: str
    os_version: str
    api_level: int
    abi: str
    status: str
    battery: int
    charging: bool
    temperature_c: float
    storage_free_gb: float
    pool_id: str
    tags: list[str]
    source: str
    automatable: bool
    last_seen: str
    reserved_by: str | None = None
    reserved_until: str | None = None
    notes: str = ""
    screen_w: int = 1080
    screen_h: int = 2400

    def available_for_jobs(self) -> bool:
        return (
            self.automatable
            and self.status == "online"
            and self.reserved_by is None
            and self.battery >= 15
            and self.temperature_c < 42
        )


@dataclass
class StepResult:
    name: str
    status: str
    duration_ms: int
    detail: str = ""


@dataclass
class DeviceRun:
    device_id: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int = 0
    steps: list[StepResult] = field(default_factory=list)
    screenshots: list[dict[str, str]] = field(default_factory=list)
    log_excerpt: str = ""
    failure: str | None = None
    visual_match: float | None = None


@dataclass
class Job:
    id: str
    name: str
    suite: str
    app_label: str
    pool_id: str | None
    device_ids: list[str]
    status: str
    created_at: str
    created_by: str
    started_at: str | None = None
    finished_at: str | None = None
    runs: list[DeviceRun] = field(default_factory=list)
    notes: str = ""


@dataclass
class Session:
    id: str
    device_id: str
    operator: str
    purpose: str
    started_at: str
    ended_at: str | None = None
    status: str = "active"


@dataclass
class AuditEvent:
    id: str
    at: str
    actor: str
    action: str
    target: str
    detail: str


@dataclass
class Alert:
    id: str
    severity: str
    device_id: str | None
    title: str
    detail: str
    at: str


def iter_devices(devices: Iterable[Device]) -> Iterable[Device]:
    return devices
