# Claude Usage Monitor

A Windows system tray app that shows your Claude Pro 5-hour utilization as a color-coded number near the clock — no browser required.

- **Green** = under 70%, **Yellow** = 70–89%, **Red** = 90%+
- Hover for full details: 5-hour %, 7-day %, both reset times, and when data was last fetched
- Polls every 2 minutes (no Claude token cost — just a metadata request)
- Reads your existing Claude Code credentials — zero configuration

## Requirements

- Windows 10 or 11
- **Python 3.10+ installed on Windows** (not WSL)
  - Download from [python.org](https://www.python.org/downloads/)
  - During install, check **"Add Python to PATH"**
- Claude Code installed and you have logged in at least once (`claude` in a terminal)

## Installation

Open **Command Prompt or PowerShell** on Windows (not WSL):

```powershell
git clone https://github.com/jomoglobal/claude-usage-monitor.git
cd claude-usage-monitor
pip install -r requirements.txt
```

You can clone it anywhere — there is no required location.

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

### Method 2 — Task Scheduler (more reliable)

1. Open **Task Scheduler** (search in Start menu)
2. Click **Create Basic Task…**
3. Name: `Claude Usage Monitor`
4. Trigger: **When I log on**
5. Action: **Start a program**
   - Program: `pythonw`
   - Arguments: `C:\path\to\claude-usage-monitor\monitor.py`
   - Start in: `C:\path\to\claude-usage-monitor`
6. Finish

## Tray icon

| Display | Meaning |
|---------|---------|
| Green number | 5-hour usage low (< 70%) |
| Yellow number | 5-hour usage getting close (≥ 70%) |
| Red number | 5-hour usage near limit (≥ 90%) |
| Gray `?` | Error — hover to see details |

Right-click the icon for **Refresh Now** or **Exit**.

Hover the icon to see full details including when the data was last successfully fetched.

## Troubleshooting

### Gray `?` instead of a number

The app is in an error state. Hover the icon to read the specific message. Common causes:

- **Token expired** — the OAuth token in `%USERPROFILE%\.claude\.credentials.json` has expired. This happens independently of your claude.ai browser session — they are separate auth systems. Fix: open any terminal and run `claude`. The monitor recovers automatically on the next poll.
- **Rate limited** — see the rate limiting section below.
- **Never successfully fetched** — if the app was rate limited from the very first poll, it has no data to display. Wait for the ban to lift (hover shows the countdown), then it will populate automatically.

### Rate limiting (HTTP 429) — the main known issue

This is the most persistent problem encountered during development. Anthropic's usage endpoint has a rate limit. If the app hits it too frequently — especially in a short burst — Anthropic issues a ban with a `Retry-After` header specifying how long to wait (sometimes up to 1 hour).

**What causes it:**
- The original 60-second poll interval worked fine during active use, but triggered the ban during debugging sessions where the app was stopped and restarted many times in quick succession
- Each restart hits the API immediately, which counts as a burst even if the ongoing poll interval is reasonable
- Clicking Refresh Now repeatedly while already rate limited resets the ban clock and extends the ban

**How the app handles it now:**
- On a 429 response, the app reads the `Retry-After` header and records a `rate_limit_until` timestamp
- It will not hit the endpoint again until that timestamp passes — not even on Refresh Now
- If there is cached data from a previous successful fetch, it keeps displaying that
- If there is no cached data (e.g. rate limited on first launch), it shows `?` with a countdown in the tooltip
- Once the ban expires, the app recovers automatically on the next poll cycle

**If you are currently rate limited:**

Check how long remains:
```bash
python3 -c "
import json, requests
with open('/mnt/c/Users/GLOBAL_HP/.claude/.credentials.json') as f:
    token = json.load(f)['claudeAiOauth']['accessToken']
resp = requests.get('https://api.anthropic.com/api/oauth/usage', headers={'Authorization': f'Bearer {token}', 'anthropic-beta': 'oauth-2025-04-20'}, timeout=15)
print('Status:', resp.status_code)
if resp.status_code == 429:
    r = int(resp.headers.get('Retry-After', 0))
    print(f'Banned — {r // 60}m {r % 60}s remaining')
else:
    print('Clear:', resp.text[:200])
"
```

Do not restart the app or click Refresh Now while banned — it will reset the clock. Just wait.

### Refresh Now not working

If Refresh Now does not update the icon, the most likely cause is an active rate limit window. The app intentionally blocks API calls during a ban. Check the tooltip — if it shows a rate limit countdown, you must wait it out.

### Stale data after a 5-hour reset

When the 5-hour window resets, the usage drops to 0%. The monitor will show the old value until the next poll (up to 2 minutes). This is expected. Hover the tooltip — the "Updated:" timestamp tells you exactly how old the data is.

### Icon not visible

Click the `^` arrow in the system tray to show hidden icons. You can drag the monitor icon out of the overflow area to keep it always visible.

### Checking the log

`monitor.log` in the repo folder records every error with a timestamp. If the icon is misbehaving, this is the first place to look:
```bash
tail -30 /home/global_hp/claude-usage-monitor/monitor.log
```

## How it works

1. Reads `%USERPROFILE%\.claude\.credentials.json` — the OAuth token Claude Code writes after login
2. Calls `GET https://api.anthropic.com/api/oauth/usage` every 2 minutes
3. Updates the tray icon color and number with the 5-hour utilization
4. On token expiry (HTTP 401), attempts auto-refresh via `claude update`, then notifies you if that fails
5. On rate limit (HTTP 429), records the `Retry-After` deadline and displays last known data until the ban lifts — Refresh Now also respects this window

## Uninstalling (current method)

There is no installer yet, so uninstall is manual — but nothing is hidden:

1. **Stop the app** — right-click the tray icon → Exit (or open Task Manager → find `pythonw.exe` → End task)
2. **Remove from startup** — whichever method you used:
   - Startup folder: press `Win+R` → type `shell:startup` → delete `startup.bat`
   - Task Scheduler: open Task Scheduler → find "Claude Usage Monitor" → right-click → Delete
3. **Delete the folder** — delete wherever you cloned the repo. That's the entire app.
4. **Optionally remove the pip packages** — only if you don't use these elsewhere:
   ```bat
   pip uninstall pystray Pillow requests pyinstaller
   ```

Nothing is written to the registry. Nothing is written outside the repo folder except the pip packages.

## Planned: proper installer (Inno Setup)

The goal is to produce a `ClaudeMonitorSetup.exe` that installs like any normal Windows app — visible in **Apps > Installed Apps** with a working uninstall button.

The build chain will be:

```
monitor.py
    ↓ PyInstaller  →  monitor.exe  (self-contained, no Python needed on target)
    ↓ Inno Setup   →  ClaudeMonitorSetup.exe  (the installer)
```

**PyInstaller** is already installed. It bundles `monitor.py` plus Python and all dependencies into a single `.exe` so the target machine needs nothing pre-installed.

**Inno Setup** still needs to be installed — download from [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php) and run the installer, accepting all defaults. The source for Inno Setup is at [github.com/jrsoftware/issrc](https://github.com/jrsoftware/issrc) but you don't need to build it from source.

Once Inno Setup is installed, the plan is to:
1. Write an Inno Setup script (`.iss` file) defining app name, version, install location, startup entry, and uninstall behavior
2. Run PyInstaller to produce `monitor.exe`
3. Run Inno Setup to produce `ClaudeMonitorSetup.exe`
4. Commit the `.iss` script to the repo; distribute `ClaudeMonitorSetup.exe`

After that, installing on any machine is: download `ClaudeMonitorSetup.exe`, double-click, done — no Python, no git, no pip required.

## Security

- Reads credentials read-only from local disk — never writes or copies them anywhere
- Makes exactly one outbound connection: `api.anthropic.com`
- No telemetry, no analytics, no third-party calls
- All source code is in `monitor.py` — easy to audit
