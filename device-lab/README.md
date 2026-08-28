# Bench — QA device lab

Local software for a **phone and tablet rack you own**. It is a test lab, not a growth or account tool.

Use it to:

- See which handsets are idle, busy, reserved, or sick (battery, heat, storage)
- Queue smoke / regression / visual / accessibility / instrumentation runs against **your** app
- Reserve a device for a timed desk session so two people do not collide
- Plug in real Android phones with `adb` when you are ready
- Dispatch the same suites from CI

It will not help with fake accounts, social farming, engagement bots, spoofed identities, or anything that breaks a platform’s rules.

## Run it

```bash
cd device-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python3 -m devicelab --host 127.0.0.1 --port 8765
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). The first load shows a **demo rack** so you can click through the product without USB hardware.

## Real phones

1. Enable USB debugging on each Android device you own.
2. Install [platform-tools](https://developer.android.com/tools/releases/platform-tools) so `adb devices` works.
3. Click **Sync USB (adb)** in the dashboard.

iOS devices can be reserved for manual QA. Automated iOS runs need a Mac and XCTest; that runner is intentionally not in this first cut.

## Suites

| Suite | What it does |
| --- | --- |
| `install_launch` | Health check, install the app under test, cold start |
| `smoke` | Launch, primary screen, rotation, background/resume |
| `regression` | Broader flows plus logcat |
| `visual_diff` | Screenshot buffers vs a baseline |
| `accessibility` | TalkBack / contrast / touch-target probe |
| `instrumentation` | `am instrument` style test APK |

Demo mode **simulates** those steps so the UI is usable in CI and on a laptop. On a USB device the `adb` adapter is the install/screenshot/log path — still only for an app you point at by package name.

## CI

```bash
curl -s http://127.0.0.1:8765/api/jobs \
  -H 'Content-Type: application/json' \
  -H 'X-Operator: github-actions' \
  -d '{
    "name": "post-merge smoke",
    "suite": "smoke",
    "app_label": "com.yourcompany.app",
    "pool_id": "pool-smoke"
  }'
```

## Tests

```bash
cd device-lab
PYTHONPATH=src python3 -m pytest -q
```

## What “advanced” means here

Compared with a pile of USB hubs and a spreadsheet:

- Pools (smoke / regression / manual) instead of one undifferentiated basket
- Jobs wait on low battery and high temperature instead of failing mysteriously
- Desk reservations with an audit trail
- Per-device reports (steps, screenshots, log excerpt, visual match)
- A CI hook that talks JSON, not a local GUI click

That is QA lab software. If you need BrowserStack-class hosted devices, this still runs next to them — it just manages the hardware on your bench.
