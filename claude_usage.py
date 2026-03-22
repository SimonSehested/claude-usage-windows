#!/usr/bin/env python3
"""
Claude AI Usage Monitor for Windows
Reads credentials from Claude Code (~/.claude/.credentials.json)
No session key or manual setup required.
"""

import os
import json
import threading
import time
import queue
import webbrowser
import subprocess
import winreg
from datetime import datetime, timezone
from typing import Optional

import requests
import tkinter as tk
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item, Menu

# ── Config ────────────────────────────────────────────────────────────────────

APP_NAME         = "ClaudeUsageMonitor"
REFRESH_INTERVAL = 300   # 5 min

CREDENTIALS_PATH = os.path.expanduser(
    os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude") + "/.credentials.json"
)

USAGE_URL   = "https://api.anthropic.com/api/oauth/usage"
PROFILE_URL = "https://api.anthropic.com/api/oauth/profile"

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

# ── Credentials ───────────────────────────────────────────────────────────────

def load_token() -> Optional[str]:
    """Read OAuth access token from Claude Code credentials file."""
    try:
        with open(CREDENTIALS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data["claudeAiOauth"]["accessToken"]
    except Exception:
        return None


def auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "anthropic-beta": "oauth-2025-04-20",
    }

# ── API ───────────────────────────────────────────────────────────────────────

def fetch_usage() -> dict:
    token = load_token()
    if not token:
        raise FileNotFoundError(
            "Claude Code credentials not found.\n"
            "Run  claude  in a terminal and log in first."
        )

    r = requests.get(USAGE_URL, headers=auth_headers(token), timeout=15)
    if r.status_code == 401:
        raise PermissionError("Token expired – run  claude  and log in again.")
    r.raise_for_status()
    return r.json()

# ── Helpers ───────────────────────────────────────────────────────────────────

def normalise(util) -> float:
    """Ensure utilization is in 0-1 range regardless of API format."""
    v = float(util)
    return v / 100.0 if v > 1.0 else v


def usage_hex(util: float) -> str:
    if util < 0.60:   return COLORS["green"]
    elif util < 0.85: return COLORS["yellow"]
    else:             return COLORS["red"]


def usage_rgb(util: float):
    c = usage_hex(util).lstrip("#")
    return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))


def fmt_reset(resets_at: Optional[str]) -> str:
    if not resets_at:
        return ""
    try:
        dt   = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        secs = (dt - datetime.now(timezone.utc)).total_seconds()
        if secs <= 0:  return "Resetting soon"
        d = int(secs // 86400)
        h = int((secs % 86400) // 3600)
        m = int((secs % 3600) // 60)
        if d:    return f"Resets in {d}d {h}h"
        elif h:  return f"Resets in {h}h {m}m"
        else:    return f"Resets in {m}m"
    except Exception:
        return ""

# ── Tray icon ─────────────────────────────────────────────────────────────────

def make_icon(five_hour: Optional[float] = None,
              seven_day: Optional[float] = None) -> Image.Image:
    """
    Outer ring = 7-day (weekly, most important)
    Inner dot  = 5-hour session colour
    """
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if seven_day is None and five_hour is None:
        draw.ellipse([4, 4, size-4, size-4], fill=(60, 60, 80, 255))
        return img

    bg    = (20, 20, 35, 255)
    track = (50, 50, 75, 255)
    # Outer arc = weekly
    sd    = seven_day if seven_day is not None else 0.0
    arc   = usage_rgb(sd) + (255,)
    # Inner dot = 5-hour
    dot   = (usage_rgb(five_hour) if five_hour is not None
             else (50, 50, 75)) + (255,)

    pad, rw = 3, 10
    draw.ellipse([pad, pad, size-pad, size-pad], fill=bg)
    draw.arc([pad+1, pad+1, size-pad-1, size-pad-1],
             start=0, end=360, fill=track, width=rw)
    if sd > 0:
        draw.arc([pad+1, pad+1, size-pad-1, size-pad-1],
                 start=-90, end=-90 + int(360 * sd),
                 fill=arc, width=rw)
    inner = pad + rw + 4
    draw.ellipse([inner, inner, size-inner, size-inner], fill=dot)
    return img

# ── Detail popup ──────────────────────────────────────────────────────────────

def _double_ring_section(parent,
                         sd_util: float, sd_resets: Optional[str],
                         fh_util: float, fh_resets: Optional[str]):
    """
    Double concentric ring:
      Outer (thick) = 7-day weekly  — most important
      Inner (thin)  = 5-hour session
    """
    size    = 150
    rw_out  = 14   # outer ring width
    rw_in   = 8    # inner ring width
    gap     = 5    # gap between rings
    pad_out = rw_out // 2 + 2
    pad_in  = pad_out + rw_out + gap

    sd_color = usage_hex(sd_util)
    fh_color = usage_hex(fh_util)
    sd_pct   = int(sd_util * 100)
    fh_pct   = int(fh_util * 100)

    frame = tk.Frame(parent, bg=COLORS["bg"])
    frame.pack(pady=(4, 2))

    cv = tk.Canvas(frame, width=size, height=size,
                   bg=COLORS["bg"], highlightthickness=0)
    cv.pack()

    # ── Outer ring: 7-day ──────────────────────────────────────────────────
    cv.create_arc(pad_out, pad_out, size-pad_out, size-pad_out,
                  start=0, extent=359.9,
                  style="arc", outline=COLORS["track"], width=rw_out)
    if sd_util > 0:
        cv.create_arc(pad_out, pad_out, size-pad_out, size-pad_out,
                      start=90, extent=-(360 * sd_util),
                      style="arc", outline=sd_color, width=rw_out)

    # ── Inner ring: 5-hour ─────────────────────────────────────────────────
    cv.create_arc(pad_in, pad_in, size-pad_in, size-pad_in,
                  start=0, extent=359.9,
                  style="arc", outline=COLORS["track"], width=rw_in)
    if fh_util > 0:
        cv.create_arc(pad_in, pad_in, size-pad_in, size-pad_in,
                      start=90, extent=-(360 * fh_util),
                      style="arc", outline=fh_color, width=rw_in)

    # ── Centre text: weekly % (most important) ─────────────────────────────
    cx = size // 2
    cv.create_text(cx, cx - 12, text=f"{sd_pct}%",
                   font=("Segoe UI", 22, "bold"), fill=sd_color)
    cv.create_text(cx, cx + 12, text="7-Day",
                   font=("Segoe UI", 8), fill=COLORS["muted"])

    # ── Labels row under ring ──────────────────────────────────────────────
    labels = tk.Frame(frame, bg=COLORS["bg"])
    labels.pack(pady=(4, 0))

    def _dot_label(parent, color, text):
        f = tk.Frame(parent, bg=COLORS["bg"])
        f.pack(side="left", padx=8)
        tk.Canvas(f, width=8, height=8, bg=COLORS["bg"],
                  highlightthickness=0).pack(side="left", pady=2)
        # draw dot
        c = tk.Canvas(f, width=10, height=10,
                      bg=COLORS["bg"], highlightthickness=0)
        c.pack(side="left")
        c.create_oval(1, 1, 9, 9, fill=color, outline="")
        tk.Label(f, text=text, font=("Segoe UI", 8),
                 bg=COLORS["bg"], fg=COLORS["muted"]).pack(side="left", padx=2)

    _dot_label(labels, sd_color, f"7d: {sd_pct}%")
    _dot_label(labels, fh_color, f"5h: {fh_pct}%")

    # ── Reset times ────────────────────────────────────────────────────────
    for rt in [fmt_reset(sd_resets), fmt_reset(fh_resets)]:
        if rt:
            tk.Label(frame, text=rt, font=("Segoe UI", 7),
                     bg=COLORS["bg"], fg=COLORS["muted"]).pack()


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

    bar_w, bar_h = 268, 8
    cv = tk.Canvas(frame, width=bar_w, height=bar_h,
                   bg=COLORS["track"], highlightthickness=0)
    cv.pack(pady=(3, 1))
    if util > 0:
        cv.create_rectangle(0, 0, max(1, int(bar_w * util)), bar_h,
                             fill=color, outline="")

    rt = fmt_reset(resets_at)
    if rt:
        tk.Label(frame, text=rt, font=("Segoe UI", 7),
                 bg=COLORS["bg"], fg=COLORS["muted"]).pack(anchor="w")


EXTRA_BAR_KEYS = [
    ("seven_day_sonnet", "7-Day Sonnet"),
    ("seven_day_opus",   "7-Day Opus"),
]


def open_detail(root: tk.Tk, usage_data, last_error, last_updated):
    sd_data  = None   # (util, resets_at)
    fh_data  = None
    bar_rows = []

    if usage_data:
        sd_v = usage_data.get("seven_day")
        fh_v = usage_data.get("five_hour")
        if sd_v and "utilization" in sd_v:
            sd_data = (normalise(sd_v["utilization"]), sd_v.get("resets_at"))
        if fh_v and "utilization" in fh_v:
            fh_data = (normalise(fh_v["utilization"]), fh_v.get("resets_at"))
        for key, label in EXTRA_BAR_KEYS:
            v = usage_data.get(key)
            if v and isinstance(v, dict) and "utilization" in v:
                bar_rows.append((label, normalise(v["utilization"]), v.get("resets_at")))

    has_rings = sd_data or fh_data
    ring_h    = 220 if has_rings else 0
    bars_h    = len(bar_rows) * 58
    err_h     = 50 if last_error else 0
    empty_h   = 30 if (not has_rings and not bar_rows and not last_error) else 0
    win_w     = 300
    win_h     = 52 + ring_h + bars_h + err_h + empty_h + 22

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg=COLORS["border"])
    win.attributes("-topmost", True)

    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{win_w}x{win_h}+{sw-win_w-14}+{sh-win_h-52}")

    inner = tk.Frame(win, bg=COLORS["bg"], padx=14, pady=10)
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    hdr = tk.Frame(inner, bg=COLORS["bg"])
    hdr.pack(fill="x", pady=(0, 6))
    tk.Label(hdr, text="Claude AI Usage", font=("Segoe UI", 11, "bold"),
             bg=COLORS["bg"], fg=COLORS["text"]).pack(side="left")
    tk.Button(hdr, text="✕", command=win.destroy,
              font=("Segoe UI", 9), bg=COLORS["bg"], fg=COLORS["muted"],
              relief="flat", cursor="hand2").pack(side="right")

    if last_error:
        tk.Label(inner, text=f"⚠  {last_error}",
                 font=("Segoe UI", 8), bg=COLORS["bg"], fg=COLORS["red"],
                 wraplength=265, justify="left").pack(anchor="w", pady=(0, 8))
    elif not has_rings and not bar_rows:
        tk.Label(inner, text="Loading usage data…",
                 font=("Segoe UI", 9), bg=COLORS["bg"],
                 fg=COLORS["muted"]).pack(anchor="w")
    else:
        sd_u, sd_r = sd_data if sd_data else (0.0, None)
        fh_u, fh_r = fh_data if fh_data else (0.0, None)
        _double_ring_section(inner, sd_u, sd_r, fh_u, fh_r)

        if bar_rows:
            tk.Frame(inner, bg=COLORS["border"], height=1).pack(
                fill="x", pady=(4, 8))
            for label, util, ra in bar_rows:
                _bar_row(inner, label, util, ra)

    if last_updated:
        tk.Label(inner, text=f"Updated {last_updated.strftime('%H:%M')}",
                 font=("Segoe UI", 7), bg=COLORS["bg"],
                 fg=COLORS["muted"]).pack(anchor="e")

    win.bind("<FocusOut>", lambda _: win.destroy())
    win.bind("<Escape>",   lambda _: win.destroy())
    win.focus_force()

# ── App ───────────────────────────────────────────────────────────────────────

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

    def _refresh(self):
        try:
            data = fetch_usage()
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

    def _push_icon(self):
        with self._lock:
            data = self.usage_data

        fh, sd = None, None
        if data:
            fh_v = data.get("five_hour")
            sd_v = data.get("seven_day")
            if fh_v and "utilization" in fh_v:
                fh = normalise(fh_v["utilization"])
            if sd_v and "utilization" in sd_v:
                sd = normalise(sd_v["utilization"])

        if self.tray:
            self.tray.icon  = make_icon(fh, sd)   # outer=7d, inner=5h
            self.tray.title = self._tooltip()

    def _tooltip(self) -> str:
        with self._lock:
            data, err = self.usage_data, self.last_error
        if err:      return "Claude Usage – Error"
        if not data: return "Claude Usage – Loading…"
        parts = []
        for key, label, _ in METRIC_KEYS[:2]:
            v = data.get(key)
            if v and "utilization" in v:
                parts.append(f"{label.split('-')[0].strip()}: {int(normalise(v['utilization'])*100)}%")
        return ("Claude Usage — " + " | ".join(parts)) if parts else "Claude Usage"

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

    def on_view(self, *_):
        with self._lock:
            d, e, u = self.usage_data, self.last_error, self.last_updated
        self._enqueue(lambda: open_detail(self.root, d, e, u))

    def on_refresh(self, *_):
        threading.Thread(target=self._refresh, daemon=True).start()

    def on_web(self, *_):
        webbrowser.open("https://claude.ai")

    # ── Autostart ─────────────────────────────────────────────────────────────

    def _autostart_enabled(self) -> bool:
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run",
                                 0, winreg.KEY_READ)
            winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            return False

    def _set_autostart(self, enable: bool):
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        if enable:
            # Use pythonw.exe so no console window appears
            pythonw = os.path.join(os.path.dirname(
                os.sys.executable), "pythonw.exe")
            script  = os.path.abspath(__file__)
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ,
                              f'"{pythonw}" "{script}"')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)

    def on_toggle_autostart(self, *_):
        self._set_autostart(not self._autostart_enabled())
        # Rebuild menu so checkmark updates
        self._rebuild_menu()

    def _rebuild_menu(self):
        checked = self._autostart_enabled()
        menu = Menu(
            item("View Usage",                  self.on_view,            default=True),
            item("Refresh Now",                 self.on_refresh),
            Menu.SEPARATOR,
            item("Open Claude.ai",              self.on_web),
            Menu.SEPARATOR,
            item("Start with Windows",          self.on_toggle_autostart,
                 checked=lambda _: self._autostart_enabled()),
            Menu.SEPARATOR,
            item("Quit",                        self.on_quit),
        )
        if self.tray:
            self.tray.menu = menu

    def on_quit(self, *_):
        self._stop.set()
        if self.tray:  self.tray.stop()
        if self.root:  self.root.after(0, self.root.destroy)

    def run(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.after(150, self._drain_queue)

        menu = Menu(
            item("View Usage",         self.on_view,              default=True),
            item("Refresh Now",        self.on_refresh),
            Menu.SEPARATOR,
            item("Open Claude.ai",     self.on_web),
            Menu.SEPARATOR,
            item("Start with Windows", self.on_toggle_autostart,
                 checked=lambda _: self._autostart_enabled()),
            Menu.SEPARATOR,
            item("Quit",               self.on_quit),
        )
        self.tray = pystray.Icon(APP_NAME, make_icon(), "Claude Usage", menu)
        threading.Thread(target=self._poll, daemon=True).start()
        self.tray.run_detached()
        self.root.mainloop()


if __name__ == "__main__":
    App().run()
