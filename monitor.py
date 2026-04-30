"""Claude Pro subscription usage monitor — Windows system tray application.

Reads the OAuth token that Claude Code stores locally and polls the Anthropic
usage endpoint every 30 seconds. Shows a color-coded icon in the system tray
(green / yellow / red) based on the higher of the 5-hour and 7-day utilization.
"""

import json
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import pystray
import requests
from PIL import Image, ImageDraw

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POLL_INTERVAL = 30  # seconds between API polls
USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"
USAGE_API_HEADERS_BASE = {"anthropic-beta": "oauth-2025-04-20"}

THRESHOLD_YELLOW = 70.0  # % at which icon turns yellow
THRESHOLD_RED = 90.0     # % at which icon turns red

# Icon colors (R, G, B)
COLOR_GREEN  = (34, 197, 94)
COLOR_YELLOW = (234, 179,  8)
COLOR_RED    = (239, 68,  68)
COLOR_GRAY   = (107, 114, 128)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class TokenExpiredError(Exception):
    pass

class APIError(Exception):
    pass


# ---------------------------------------------------------------------------
# Token reading
# ---------------------------------------------------------------------------

def _credentials_path() -> str:
    """Return the path to Claude Code's credentials file."""
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
    if config_dir:
        return os.path.join(config_dir, ".credentials.json")

    if platform.system() == "Windows":
        base = os.environ.get("USERPROFILE", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")

    return os.path.join(base, ".claude", ".credentials.json")


def read_token() -> str:
    """Read the OAuth access token from Claude Code's credentials file."""
    path = _credentials_path()
    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Credentials file not found: {path}\n"
            "Make sure Claude Code is installed and you are logged in."
        )
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    try:
        return data["claudeAiOauth"]["accessToken"]
    except (KeyError, TypeError) as e:
        raise ValueError(f"Unexpected credentials format: {e}") from e


# ---------------------------------------------------------------------------
# API call
# ---------------------------------------------------------------------------

def fetch_usage(token: str) -> dict:
    """Query the Anthropic OAuth usage endpoint.

    Returns a dict with keys: five_hour_pct, seven_day_pct,
    five_hour_resets_at (str ISO8601), seven_day_resets_at (str ISO8601).
    Raises TokenExpiredError on 401, APIError on anything else unexpected.
    """
    headers = {**USAGE_API_HEADERS_BASE, "Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(USAGE_API_URL, headers=headers, timeout=15)
    except requests.RequestException as e:
        raise APIError(f"Network error: {e}") from e

    if resp.status_code == 401:
        raise TokenExpiredError("OAuth token rejected (401)")

    if not resp.ok:
        raise APIError(f"API returned {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    return {
        "five_hour_pct":       float(data.get("five_hour", {}).get("utilization", 0)),
        "seven_day_pct":       float(data.get("seven_day", {}).get("utilization", 0)),
        "five_hour_resets_at": data.get("five_hour", {}).get("resets_at", ""),
        "seven_day_resets_at": data.get("seven_day", {}).get("resets_at", ""),
    }


# ---------------------------------------------------------------------------
# Icon generation
# ---------------------------------------------------------------------------

def make_icon(color: tuple) -> Image.Image:
    """Generate a 64×64 PIL image: white background with a filled color circle."""
    img = Image.new("RGBA", (64, 64), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=color + (255,))
    return img


def _color_for(five_pct: float, seven_pct: float) -> tuple:
    peak = max(five_pct, seven_pct)
    if peak >= THRESHOLD_RED:
        return COLOR_RED
    if peak >= THRESHOLD_YELLOW:
        return COLOR_YELLOW
    return COLOR_GREEN


# ---------------------------------------------------------------------------
# Tooltip formatting
# ---------------------------------------------------------------------------

def _fmt_reset(iso: str) -> str:
    """Convert ISO8601 UTC string to a human-readable local time + countdown."""
    if not iso:
        return "unknown"
    try:
        dt_utc = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = dt_utc - now
        total = int(delta.total_seconds())
        if total <= 0:
            return "resetting soon"
        h, rem = divmod(total, 3600)
        m = rem // 60
        local_str = dt_utc.astimezone().strftime("%H:%M")
        if h > 0:
            countdown = f"{h}h {m}m"
        else:
            countdown = f"{m}m"
        return f"{local_str} (in {countdown})"
    except Exception:
        return iso


def format_tooltip(five_pct: float, seven_pct: float,
                   five_reset: str, seven_reset: str) -> str:
    lines = [
        "Claude Usage Monitor",
        f"5-hour:  {five_pct:.1f}%  — resets {_fmt_reset(five_reset)}",
        f"7-day:   {seven_pct:.1f}%  — resets {_fmt_reset(seven_reset)}",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Token refresh via CLI
# ---------------------------------------------------------------------------

def refresh_token_via_cli() -> bool:
    """Attempt to refresh the OAuth token by running 'claude update'."""
    try:
        result = subprocess.run(
            ["claude", "update"],
            timeout=60,
            capture_output=True,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Background poll loop
# ---------------------------------------------------------------------------

class PollState:
    def __init__(self):
        self.icon = None          # pystray.Icon reference, set after creation
        self.force_refresh = threading.Event()
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def trigger_refresh(self):
        self.force_refresh.set()


_state = PollState()


def _update_icon(five_pct: float, seven_pct: float,
                 five_reset: str, seven_reset: str):
    if _state.icon is None:
        return
    color = _color_for(five_pct, seven_pct)
    _state.icon.icon = make_icon(color)
    _state.icon.title = format_tooltip(five_pct, seven_pct, five_reset, seven_reset)


def _set_error_icon(message: str):
    if _state.icon is None:
        return
    _state.icon.icon = make_icon(COLOR_GRAY)
    _state.icon.title = f"Claude Usage Monitor\n{message}"


def poll_loop():
    token_expired_notified = False

    while not _state._stop.is_set():
        try:
            token = read_token()
            usage = fetch_usage(token)
            token_expired_notified = False
            _update_icon(
                usage["five_hour_pct"], usage["seven_day_pct"],
                usage["five_hour_resets_at"], usage["seven_day_resets_at"],
            )

        except TokenExpiredError:
            if not token_expired_notified:
                _set_error_icon("Token expired — attempting refresh…")
                if _state.icon:
                    _state.icon.notify(
                        "Claude token expired — refreshing…",
                        "Claude Usage Monitor",
                    )
                refreshed = refresh_token_via_cli()
                if refreshed:
                    # retry immediately on next loop iteration
                    _state.force_refresh.set()
                else:
                    _set_error_icon("Login required — run 'claude' to re-authenticate")
                    if _state.icon:
                        _state.icon.notify(
                            "Could not refresh token. Please run 'claude' to log in.",
                            "Claude Usage Monitor",
                        )
                    token_expired_notified = True

        except FileNotFoundError as e:
            _set_error_icon(str(e))

        except APIError as e:
            _set_error_icon(f"API error: {e}")

        except Exception as e:
            _set_error_icon(f"Unexpected error: {e}")

        # Wait for next poll or forced refresh
        _state.force_refresh.wait(timeout=POLL_INTERVAL)
        _state.force_refresh.clear()


# ---------------------------------------------------------------------------
# Menu callbacks
# ---------------------------------------------------------------------------

def on_refresh(icon, item):
    _state.trigger_refresh()


def on_exit(icon, item):
    _state.stop()
    icon.stop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    menu = pystray.Menu(
        pystray.MenuItem("Refresh Now", on_refresh),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit),
    )

    icon = pystray.Icon(
        name="ClaudeUsageMonitor",
        icon=make_icon(COLOR_GRAY),
        title="Claude Usage Monitor\nLoading…",
        menu=menu,
    )
    _state.icon = icon

    t = threading.Thread(target=poll_loop, daemon=True)
    t.start()

    # pystray.Icon.run() must be called on the main thread
    icon.run()


if __name__ == "__main__":
    main()
