#!/usr/bin/env python3
"""
Claude AI Usage Monitor for Windows
System tray app that shows your claude.ai subscription usage in real time.
"""

import sys
import threading
import time
import queue
import webbrowser
from datetime import datetime, timezone
from typing import Optional

import requests
import keyring
import tkinter as tk
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item, Menu

# ── Configuration ─────────────────────────────────────────────────────────────

APP_NAME        = "ClaudeUsageMonitor"
KEYRING_SERVICE = "ClaudeUsageMonitor"
KEYRING_KEY     = "session_key"
REFRESH_INTERVAL = 300   # seconds between auto-refreshes (5 min)

COLORS = {
    "bg":     "#0f0f1a",
    "bg2":    "#1a1a2e",
    "track":  "#2d2d4e",
    "text":   "#e2e8f0",
    "muted":  "#64748b",
    "green":  "#22c55e",
    "yellow": "#eab308",
    "red":    "#ef4444",
    "purple": "#7c3aed",
    "border": "#334155",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def usage_hex(util: float) -> str:
    if util < 0.60:
        return COLORS["green"]
    elif util < 0.85:
        return COLORS["yellow"]
    else:
        return COLORS["red"]


def usage_rgb(util: float):
    c = usage_hex(util).lstrip("#")
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


def fmt_reset(resets_at: Optional[str]) -> str:
    if not resets_at:
        return ""
    try:
        dt  = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        secs = (dt - now).total_seconds()
        if secs <= 0:
            return "Resetting soon"
        d = int(secs // 86400)
        h = int((secs % 86400) // 3600)
        m = int((secs % 3600) // 60)
        if d:    return f"Resets in {d}d {h}h"
        elif h:  return f"Resets in {h}h {m}m"
        else:    return f"Resets in {m}m"
    except Exception:
        return ""

# ── Claude API ────────────────────────────────────────────────────────────────

def fetch_usage(session_key: str) -> dict:
    """
    Fetches usage data from the internal claude.ai API.
    Returns a dict with keys like fiveHour, sevenDay, sevenDaySonnet, etc.
    Each value is { utilization: float 0-1, resetsAt: ISO8601 string }
    """
    headers = {
        "accept": "*/*",
        "content-type": "application/json",
        "anthropic-client-platform": "web_claude_ai",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    cookies = {"sessionKey": session_key}

    r = requests.get(
        "https://claude.ai/api/organizations",
        headers=headers, cookies=cookies, timeout=15,
    )
    if r.status_code in (401, 403):
        raise PermissionError("Session key is invalid or expired – please update it in Settings.")
    r.raise_for_status()

    orgs = r.json()
    if not orgs:
        raise ValueError("No organisations found in your Claude account.")
    org_id = orgs[0]["uuid"]

    r = requests.get(
        f"https://claude.ai/api/organizations/{org_id}/usage",
        headers=headers, cookies=cookies, timeout=15,
    )
    if r.status_code in (401, 403):
        raise PermissionError("Session key is invalid or expired – please update it in Settings.")
    r.raise_for_status()
    return r.json()


# ── Tray icon image ───────────────────────────────────────────────────────────

def make_icon(five_hour: Optional[float] = None,
              seven_day: Optional[float] = None) -> Image.Image:
    """
    64×64 RGBA icon.
    Outer arc  = 5-hour session utilisation
    Inner dot  = 7-day utilisation colour
    Grey       = loading / no data
    """
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if five_hour is None:
        draw.ellipse([4, 4, size-4, size-4], fill=(60, 60, 80, 255))
        return img

    bg    = (20, 20, 35, 255)
    track = (50, 50, 75, 255)
    arc   = usage_rgb(five_hour) + (255,)
    dot   = (usage_rgb(seven_day) if seven_day is not None
             else (50, 50, 75)) + (255,)

    pad  = 3
    rw   = 10   # ring width

    draw.ellipse([pad, pad, size-pad, size-pad], fill=bg)
    draw.arc([pad+1, pad+1, size-pad-1, size-pad-1],
             start=0, end=360, fill=track, width=rw)

    if five_hour > 0:
        end_a = -90 + int(360 * five_hour)
        draw.arc([pad+1, pad+1, size-pad-1, size-pad-1],
                 start=-90, end=end_a, fill=arc, width=rw)

    inner = pad + rw + 4
    draw.ellipse([inner, inner, size-inner, size-inner], fill=dot)
    return img


# ── Settings window ───────────────────────────────────────────────────────────

def open_settings(root: tk.Tk, on_save=None):
    win = tk.Toplevel(root)
    win.title("Claude Usage – Settings")
    win.geometry("480x230")
    win.resizable(False, False)
    win.configure(bg=COLORS["bg2"])
    win.attributes("-topmost", True)

    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"480x230+{(sw-480)//2}+{(sh-230)//2}")

    tk.Label(win, text="Session Key",
             font=("Segoe UI", 13, "bold"),
             bg=COLORS["bg2"], fg=COLORS["text"]).pack(anchor="w", padx=18, pady=(16, 2))

    info = (
        "How to get your session key:\n"
        "1. Open claude.ai in your browser and make sure you're logged in\n"
        "2. Press F12  →  Network tab  →  reload the page (F5)\n"
        "3. Find a request named 'usage'  →  Request Headers  →  Cookie\n"
        "4. Copy the value after  sessionKey=  (starts with sk-ant-sid01-…)\n"
        "   OR: Application tab → Cookies → claude.ai → sessionKey"
    )
    tk.Label(win, text=info, font=("Segoe UI", 8),
             bg=COLORS["bg2"], fg=COLORS["muted"],
             justify="left").pack(anchor="w", padx=18, pady=(0, 8))

    current = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY) or ""
    var = tk.StringVar(value=current)

    entry = tk.Entry(win, textvariable=var, font=("Consolas", 8),
                     bg=COLORS["track"], fg=COLORS["text"],
                     insertbackground=COLORS["text"], relief="flat",
                     show="•" if current else "")
    entry.pack(fill="x", padx=18, ipady=7)

    def toggle():
        entry.configure(show="" if entry.cget("show") == "•" else "•")

    def save():
        raw = var.get().strip()
        if not raw:
            return
        # Accept full cookie string: strip key name and extra pairs
        if "sessionKey=" in raw:
            raw = raw.split("sessionKey=", 1)[1].split(";", 1)[0].strip()
        raw = raw.strip('"').strip("'")
        keyring.set_password(KEYRING_SERVICE, KEYRING_KEY, raw)
        win.destroy()
        if on_save:
            on_save()

    bf = tk.Frame(win, bg=COLORS["bg2"])
    bf.pack(anchor="w", padx=18, pady=(10, 0))

    for label, cmd, bg in [
        ("Save",        save,        COLORS["purple"]),
        ("Show/Hide",   toggle,      COLORS["track"]),
        ("Cancel",      win.destroy, COLORS["track"]),
    ]:
        tk.Button(bf, text=label, command=cmd,
                  bg=bg, fg="white", font=("Segoe UI", 9),
                  relief="flat", padx=14, pady=5,
                  cursor="hand2").pack(side="left", padx=(0, 6))


# ── Detail popup ──────────────────────────────────────────────────────────────

def _bar_row(parent, label: str, util: float, resets_at: Optional[str]):
    frame = tk.Frame(parent, bg=COLORS["bg"])
    frame.pack(fill="x", pady=(0, 6))

    pct   = int(util * 100)
    color = usage_hex(util)

    row1 = tk.Frame(frame, bg=COLORS["bg"])
    row1.pack(fill="x")
    tk.Label(row1, text=label, font=("Segoe UI", 9),
             bg=COLORS["bg"], fg=COLORS["text"]).pack(side="left")
    tk.Label(row1, text=f"{pct}%", font=("Segoe UI", 9, "bold"),
             bg=COLORS["bg"], fg=color).pack(side="right")

    bar_w, bar_h = 268, 7
    cv = tk.Canvas(frame, width=bar_w, height=bar_h,
                   bg=COLORS["track"], highlightthickness=0)
    cv.pack(pady=(2, 1))
    fill_w = max(1, int(bar_w * util)) if util > 0 else 0
    if fill_w:
        cv.create_rectangle(0, 0, fill_w, bar_h, fill=color, outline="")

    rt = fmt_reset(resets_at)
    if rt:
        tk.Label(frame, text=rt, font=("Segoe UI", 7),
                 bg=COLORS["bg"], fg=COLORS["muted"]).pack(anchor="w")


def open_detail(root: tk.Tk, usage_data, last_error, last_updated):
    METRIC_KEYS = [
        ("fiveHour",       "5-Hour Session"),
        ("sevenDay",       "7-Day Limit"),
        ("sevenDaySonnet", "7-Day Sonnet"),
        ("sevenDayOpus",   "7-Day Opus"),
        ("extraUsage",     "Extra Usage"),
    ]

    metrics = []
    if usage_data:
        for key, label in METRIC_KEYS:
            v = usage_data.get(key)
            if v and isinstance(v, dict) and "utilization" in v:
                metrics.append((label, v["utilization"], v.get("resetsAt")))

    n      = max(len(metrics), 1)
    win_w  = 300
    win_h  = 60 + n * 62 + (30 if last_error else 0) + 22

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg=COLORS["border"])
    win.attributes("-topmost", True)

    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{win_w}x{win_h}+{sw-win_w-14}+{sh-win_h-52}")

    inner = tk.Frame(win, bg=COLORS["bg"], padx=14, pady=10)
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    # Header
    hdr = tk.Frame(inner, bg=COLORS["bg"])
    hdr.pack(fill="x", pady=(0, 8))
    tk.Label(hdr, text="Claude AI Usage", font=("Segoe UI", 11, "bold"),
             bg=COLORS["bg"], fg=COLORS["text"]).pack(side="left")
    tk.Button(hdr, text="✕", command=win.destroy,
              font=("Segoe UI", 9), bg=COLORS["bg"], fg=COLORS["muted"],
              relief="flat", cursor="hand2", padx=2, pady=0).pack(side="right")

    if last_error:
        tk.Label(inner, text=f"⚠  {last_error}",
                 font=("Segoe UI", 8), bg=COLORS["bg"], fg=COLORS["red"],
                 wraplength=260, justify="left").pack(anchor="w", pady=(0, 8))
    elif not metrics:
        tk.Label(inner, text="Loading usage data…",
                 font=("Segoe UI", 9), bg=COLORS["bg"],
                 fg=COLORS["muted"]).pack(anchor="w")
    else:
        for label, util, resets_at in metrics:
            _bar_row(inner, label, util, resets_at)

    if last_updated:
        tk.Label(inner, text=f"Updated {last_updated.strftime('%H:%M')}",
                 font=("Segoe UI", 7), bg=COLORS["bg"],
                 fg=COLORS["muted"]).pack(anchor="e")

    win.bind("<FocusOut>", lambda _: win.destroy())
    win.bind("<Escape>",   lambda _: win.destroy())
    win.focus_force()


# ── Application ───────────────────────────────────────────────────────────────

class App:
    def __init__(self):
        self.usage_data:   Optional[dict]     = None
        self.last_error:   Optional[str]      = None
        self.last_updated: Optional[datetime] = None
        self._lock   = threading.Lock()
        self._stop   = threading.Event()
        self._queue  = queue.Queue()
        self.tray:   Optional[pystray.Icon] = None
        self.root:   Optional[tk.Tk]        = None

    # ── data ─────────────────────────────────────────────────────────────────

    def _refresh(self):
        sk = keyring.get_password(KEYRING_SERVICE, KEYRING_KEY)
        if not sk:
            with self._lock:
                self.last_error  = "No session key set – right-click the tray icon → Settings"
                self.usage_data  = None
            self._push_icon()
            return
        try:
            data = fetch_usage(sk)
            with self._lock:
                self.usage_data   = data
                self.last_error   = None
                self.last_updated = datetime.now()
        except Exception as e:
            with self._lock:
                self.last_error = str(e)
        self._push_icon()

    def _poll(self):
        self._refresh()
        while not self._stop.wait(REFRESH_INTERVAL):
            self._refresh()

    # ── icon ─────────────────────────────────────────────────────────────────

    def _push_icon(self):
        with self._lock:
            data = self.usage_data
        fh = data["fiveHour"]["utilization"] if data and "fiveHour" in data else None
        sd = data["sevenDay"]["utilization"] if data and "sevenDay" in data else None
        img = make_icon(fh, sd)
        if self.tray:
            self.tray.icon  = img
            self.tray.title = self._tooltip()

    def _tooltip(self) -> str:
        with self._lock:
            data, err = self.usage_data, self.last_error
        if err:   return "Claude Usage – Error"
        if not data: return "Claude Usage – Loading…"
        parts = []
        if "fiveHour" in data:
            parts.append(f"5h: {int(data['fiveHour']['utilization']*100)}%")
        if "sevenDay" in data:
            parts.append(f"7d: {int(data['sevenDay']['utilization']*100)}%")
        return ("Claude Usage — " + " | ".join(parts)) if parts else "Claude Usage"

    # ── GUI queue (all tk calls must happen on the main thread) ──────────────

    def _enqueue(self, fn):
        self._queue.put(fn)

    def _drain_queue(self):
        try:
            while True:
                self._queue.get_nowait()()
        except queue.Empty:
            pass
        if self.root:
            self.root.after(150, self._drain_queue)

    # ── tray callbacks ───────────────────────────────────────────────────────

    def on_view(self, *_):
        with self._lock:
            d, e, u = self.usage_data, self.last_error, self.last_updated
        self._enqueue(lambda: open_detail(self.root, d, e, u))

    def on_refresh(self, *_):
        threading.Thread(target=self._refresh, daemon=True).start()

    def on_settings(self, *_):
        self._enqueue(lambda: open_settings(
            self.root,
            on_save=lambda: threading.Thread(target=self._refresh, daemon=True).start(),
        ))

    def on_web(self, *_):
        webbrowser.open("https://claude.ai")

    def on_quit(self, *_):
        self._stop.set()
        if self.tray:
            self.tray.stop()
        if self.root:
            self.root.after(0, self.root.destroy)

    # ── run ──────────────────────────────────────────────────────────────────

    def run(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.after(150, self._drain_queue)

        menu = Menu(
            item("View Usage",       self.on_view,     default=True),
            item("Refresh Now",      self.on_refresh),
            Menu.SEPARATOR,
            item("Settings…",        self.on_settings),
            item("Open Claude.ai",   self.on_web),
            Menu.SEPARATOR,
            item("Quit",             self.on_quit),
        )
        self.tray = pystray.Icon(APP_NAME, make_icon(), "Claude Usage", menu)

        threading.Thread(target=self._poll, daemon=True).start()

        # Open settings automatically on first run (no session key yet)
        if not keyring.get_password(KEYRING_SERVICE, KEYRING_KEY):
            def _delayed_settings():
                time.sleep(1.5)
                self._enqueue(lambda: open_settings(
                    self.root,
                    on_save=lambda: threading.Thread(
                        target=self._refresh, daemon=True).start(),
                ))
            threading.Thread(target=_delayed_settings, daemon=True).start()

        self.tray.run_detached()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
