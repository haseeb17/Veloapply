from __future__ import annotations

import re
import shutil
import subprocess
from uuid import uuid4

from .models import Device, iso
from .store import Store


def adb_available() -> bool:
    return shutil.which("adb") is not None


def _run(args: list[str], timeout: float = 8.0) -> str:
    completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "adb command failed")
    return completed.stdout


def list_adb_serials() -> list[tuple[str, str]]:
    if not adb_available():
        return []
    output = _run(["adb", "devices", "-l"])
    found: list[tuple[str, str]] = []
    for line in output.splitlines()[1:]:
        line = line.strip()
        if not line or "offline" in line or "unauthorized" in line:
            continue
        if "\tdevice" in line or " device " in line:
            serial = line.split()[0]
            found.append((serial, line))
    return found


def _prop(serial: str, key: str, default: str = "") -> str:
    try:
        value = _run(["adb", "-s", serial, "shell", "getprop", key]).strip()
        return value or default
    except Exception:
        return default


def device_from_adb(serial: str, extra: str) -> Device:
    model = _prop(serial, "ro.product.model", serial)
    manufacturer = _prop(serial, "ro.product.manufacturer", "Android")
    version = _prop(serial, "ro.build.version.release", "?")
    sdk = _prop(serial, "ro.build.version.sdk", "0")
    abi = _prop(serial, "ro.product.cpu.abi", "arm64-v8a")
    product = _prop(serial, "ro.product.device", model)
    try:
        api_level = int(sdk)
    except ValueError:
        api_level = 0
    slug = re.sub(r"[^a-z0-9]+", "-", serial.lower())[:24]
    form = "tablet" if "tablet" in model.lower() or "tab" in model.lower() else "phone"
    return Device(
        id=f"adb-{slug}"[:32] or f"adb-{uuid4().hex[:8]}",
        serial=serial,
        name=model,
        manufacturer=manufacturer.title(),
        model=product,
        form_factor=form,
        os="Android",
        os_version=version,
        api_level=api_level,
        abi=abi,
        status="online",
        battery=50,
        charging=False,
        temperature_c=32.0,
        storage_free_gb=8.0,
        pool_id="pool-smoke",
        tags=["usb", "owned-device"],
        source="adb",
        automatable=True,
        last_seen=iso(),
        notes=extra,
    )


def refresh_adb(store: Store) -> list[str]:
    added: list[str] = []
    try:
        serials = list_adb_serials()
    except Exception:
        return added
    for serial, extra in serials:
        device = device_from_adb(serial, extra)
        store.upsert_device(device)
        added.append(serial)
    return added


def screenshot_png(serial: str) -> bytes:
    completed = subprocess.run(
        ["adb", "-s", serial, "exec-out", "screencap", "-p"],
        capture_output=True,
        timeout=12,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        raise RuntimeError("screenshot failed")
    return completed.stdout
