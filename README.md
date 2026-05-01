# Claude Usage Monitor

A Windows system tray app that shows your Claude Pro 5-hour utilization as a color-coded number near the clock — no browser required.

- **Green** = under 70%, **Yellow** = 70–89%, **Red** = 90%+
- Hover for full details: 5-hour %, 7-day %, and both reset times
- Polls every 60 seconds (no Claude token cost — just a metadata request)
- Reads your existing Claude Code credentials — zero configuration

## Requirements

- Windows 10 or 11
- **Python 3.10+ installed on Windows** (not WSL)
  - Download from [python.org](https://www.python.org/downloads/)
  - During install, check **"Add Python to PATH"**
- Claude Code installed and you have logged in at least once (`claude` in a terminal)

## Installation

Open **Command Prompt or PowerShell** on Windows (not WSL):

```bat
cd %USERPROFILE%
git clone https://github.com/jomoglobal/claude-usage-monitor.git
cd claude-usage-monitor
pip install -r requirements.txt
```

## Running

```bat
pythonw monitor.py
```

`pythonw` runs Python without a console window — the app appears only in the system tray (bottom-right near the clock). Click the `^` arrow to find it if it's hidden among collapsed icons.

To run with a visible console for debugging:

```bat
python monitor.py
```

## Adding to Windows Startup

### Method 1 — Startup folder (simplest)

1. Edit `startup.bat` — update the path to match where you cloned the repo
2. Press `Win + R`, type `shell:startup`, press Enter
3. Copy `startup.bat` into the folder that opened

The monitor launches automatically every time you log in.

### Method 2 — Task Scheduler (more reliable, survives reboots cleanly)

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task…**
3. Name: `Claude Usage Monitor`
4. Trigger: **When I log on**
5. Action: **Start a program**
   - Program: `pythonw`
   - Arguments: `C:\Users\YourName\claude-usage-monitor\monitor.py`
   - Start in: `C:\Users\YourName\claude-usage-monitor`
6. Finish

## Tray icon

| Display | Meaning |
|---------|---------|
| Green number | 5-hour usage low |
| Yellow number | 5-hour usage getting close (≥ 70%) |
| Red number | 5-hour usage near limit (≥ 90%) |
| Gray `?` | Error — hover to see details |

Right-click the icon for **Refresh Now** or **Exit**.

## Troubleshooting

**Gray `?` on startup** — Claude Code's token has expired. Open a terminal and run `claude` to refresh it. The monitor will recover automatically within 60 seconds.

**Icon not visible** — click the `^` arrow in the system tray to show hidden icons. You can drag the Claude monitor icon out to keep it always visible.

**Check the log** — if something seems wrong, open `monitor.log` in the repo folder. It records every error with a timestamp.

## How it works

1. Reads `%USERPROFILE%\.claude\.credentials.json` — the OAuth token Claude Code writes after login
2. Calls `GET https://api.anthropic.com/api/oauth/usage` with that token every 60 seconds
3. Updates the tray icon color and number with the 5-hour utilization result
4. On token expiry (HTTP 401), attempts auto-refresh via `claude update`, then notifies you if that fails
5. On rate limit (HTTP 429), silently keeps the last good value and retries next interval

## Security

- Reads credentials read-only from local disk — never writes or copies them anywhere
- Makes exactly one outbound connection: `api.anthropic.com`
- No telemetry, no analytics, no third-party calls
- All source code is in `monitor.py` (~250 lines) — easy to audit
