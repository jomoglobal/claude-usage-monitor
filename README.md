# Claude Usage Monitor

A Windows system tray app that shows your Claude Pro subscription utilization at a glance — no browser required.

- Color-coded icon: green (< 70%), yellow (70–89%), red (≥ 90%)
- Hover tooltip: 5-hour %, 7-day %, and both reset times
- Auto-refreshes every 30 seconds (no Claude token cost)
- Reads your existing Claude Code credentials — zero configuration

## Requirements

- Windows 11
- Python 3.10+ installed on **Windows** (not WSL)
  - Download from [python.org](https://www.python.org/downloads/) — check "Add Python to PATH" during install
- Claude Code installed and logged in (`claude login` in a terminal)

## Installation

Open **Command Prompt** or **PowerShell** on Windows:

```bat
cd %USERPROFILE%
git clone https://github.com/josephmontague/claude-usage-monitor.git
cd claude-usage-monitor
pip install -r requirements.txt
```

## Running

```bat
pythonw monitor.py
```

`pythonw` runs Python without a console window — the app appears only in the system tray (bottom-right, near the clock). You may need to click the `^` arrow to find it if it's hidden.

To run with a visible console for debugging:

```bat
python monitor.py
```

## Adding to Windows Startup

### Method 1 — Startup folder (simplest)

1. Press `Win + R`, type `shell:startup`, press Enter
2. Edit `startup.bat` — update `MONITOR_PATH` to the full path where you cloned this repo
3. Copy `startup.bat` into the Startup folder that opened

The monitor will launch automatically every time you log in to Windows.

### Method 2 — Task Scheduler (more reliable)

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task…**
3. Name: `Claude Usage Monitor`
4. Trigger: **When I log on**
5. Action: **Start a program**
   - Program: `pythonw`
   - Arguments: `C:\Users\<you>\claude-usage-monitor\monitor.py`
   - Start in: `C:\Users\<you>\claude-usage-monitor`
6. Finish

## How It Works

1. Reads `%USERPROFILE%\.claude\.credentials.json` — the OAuth token Claude Code stores after `claude login`
2. Calls `GET https://api.anthropic.com/api/oauth/usage` with that token every 30 seconds
3. Updates the tray icon color and tooltip with the result
4. On token expiry (HTTP 401), attempts to refresh via `claude update` and notifies you if that fails

## Security

- Reads credentials read-only from local disk; never writes or copies them anywhere
- Makes exactly one outbound connection: `api.anthropic.com`
- No telemetry, no analytics, no third-party calls
- All source code is in `monitor.py` (~220 lines) — easy to audit

## Tray Menu

- **Refresh Now** — polls the API immediately instead of waiting for the next 30-second cycle
- **Exit** — stops the monitor and removes the tray icon
