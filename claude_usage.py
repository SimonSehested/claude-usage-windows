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
import winreg
import ctypes
import ctypes.wintypes
from datetime import datetime, timezone
from typing import Optional

import requests
import keyring
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
import pystray
from pystray import MenuItem as item, Menu

# ── Config ────────────────────────────────────────────────────────────────────

APP_NAME         = "ClaudeUsageMonitor"
KEYRING_SERVICE  = "ClaudeUsageMonitor"
KEYRING_KEY      = "session_key"
REFRESH_INTERVAL = 300

CREDENTIALS_PATH = os.path.expanduser(
    os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude") + "/.credentials.json"
)
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"

# iOS Dark Mode — exact Apple HIG values
COLORS = {
    "bg":              "#1C1C1E",   # systemBackground
    "bg2":             "#2C2C2E",   # secondarySystemBackground  (cards)
    "track":           "#3A3A3C",   # tertiarySystemBackground
    "text":            "#FFFFFF",
    "muted":           "#8E8E93",   # secondaryLabel
    "separator":       "#38383A",
    "green":           "#30D158",   # systemGreen
    "yellow":          "#FFD60A",   # systemYellow
    "red":             "#FF453A",   # systemRed
    "transparent_key": "#010101",   # window punch-out — never used in design
}

# Popup geometry
POPUP_W   = 320
RING_SIZE = 180
SCALE     = 4          # supersampling factor for PIL rendering
BAR_W     = 284
BAR_H     = 10

# ── Helpers ───────────────────────────────────────────────────────────────────

def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def usage_hex(util: float) -> str:
    if util < 0.60:   return COLORS["green"]
    elif util < 0.85: return COLORS["yellow"]
    else:             return COLORS["red"]


def usage_rgb(util: float):
    return _hex_to_rgb(usage_hex(util))


def normalise(v) -> float:
    v = float(v)
    return v / 100.0 if v > 1.0 else v


def fmt_reset(resets_at: Optional[str]) -> str:
    if not resets_at:
        return ""
    try:
        dt   = datetime.fromisoformat(resets_at.replace("Z", "+00:00"))
        secs = (dt - datetime.now(timezone.utc)).total_seconds()
        if secs <= 0:  return "Resetting soon"
        d, h = int(secs // 86400), int((secs % 86400) // 3600)
        m    = int((secs % 3600) // 60)
        if d:   return f"Resets in {d}d {h}h"
        elif h: return f"Resets in {h}h {m}m"
        else:   return f"Resets in {m}m"
    except Exception:
        return ""

# ── Credentials & API ─────────────────────────────────────────────────────────

def load_token() -> Optional[str]:
    try:
        with open(CREDENTIALS_PATH, encoding="utf-8") as f:
            return json.load(f)["claudeAiOauth"]["accessToken"]
    except Exception:
        return None


def fetch_usage() -> dict:
    token = load_token()
    if not token:
        raise FileNotFoundError(
            "Claude Code credentials not found.\n"
            "Run  claude  in a terminal and log in first."
        )
    r = requests.get(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "anthropic-beta": "oauth-2025-04-20",
        },
        timeout=15,
    )
    if r.status_code == 401:
        raise PermissionError("Token expired – run  claude  in a terminal.")
    r.raise_for_status()
    return r.json()

# ── PIL rendering helpers ─────────────────────────────────────────────────────

def _apply_dwm_style(hwnd: int):
    """Apply Windows 11 native rounded corners and drop shadow to a borderless window."""
    try:
        # Rounded corners (Windows 11+)
        DWMWA_WINDOW_CORNER_PREFERENCE = 33
        DWMWCP_ROUND = 2
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_WINDOW_CORNER_PREFERENCE,
            ctypes.byref(ctypes.c_int(DWMWCP_ROUND)), 4,
        )
        # Drop shadow via DWM frame extension
        class MARGINS(ctypes.Structure):
            _fields_ = [("cxLeftWidth", ctypes.c_int), ("cxRightWidth", ctypes.c_int),
                        ("cyTopHeight", ctypes.c_int), ("cyBottomHeight", ctypes.c_int)]
        ctypes.windll.dwmapi.DwmExtendFrameIntoClientArea(
            hwnd, ctypes.byref(MARGINS(0, 0, 0, 1))
        )
    except Exception:
        pass


def _render_ring_image(sd_util: float, fh_util: float) -> Image.Image:
    """
    Anti-aliased concentric rings at 4× scale, downsampled with LANCZOS.
    Outer ring = 7-day weekly, inner ring = 5-hour session.
    """
    s      = RING_SIZE * SCALE
    img    = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)

    rw_out = 22 * SCALE
    rw_in  = 13 * SCALE
    gap    =  7 * SCALE
    p_out  = rw_out // 2 + 2 * SCALE
    p_in   = p_out + rw_out + gap

    track_rgba = _hex_to_rgb(COLORS["track"]) + (255,)

    def arc_rgba(util):
        return usage_rgb(util) + (255,)

    # Outer track + arc
    draw.arc([p_out, p_out, s-p_out, s-p_out],
             start=0, end=360, fill=track_rgba, width=rw_out)
    if sd_util > 0:
        draw.arc([p_out, p_out, s-p_out, s-p_out],
                 start=-90, end=-90 + 360 * sd_util,
                 fill=arc_rgba(sd_util), width=rw_out)

    # Inner track + arc
    draw.arc([p_in, p_in, s-p_in, s-p_in],
             start=0, end=360, fill=track_rgba, width=rw_in)
    if fh_util > 0:
        draw.arc([p_in, p_in, s-p_in, s-p_in],
                 start=-90, end=-90 + 360 * fh_util,
                 fill=arc_rgba(fh_util), width=rw_in)

    return img.resize((RING_SIZE, RING_SIZE), Image.LANCZOS)


def _render_pill_bar(util: float, color_hex: str) -> Image.Image:
    """
    Anti-aliased pill-shaped progress bar, 4× supersampled.
    Returns BAR_W × BAR_H image.
    """
    sw, sh = BAR_W * SCALE, BAR_H * SCALE
    r      = sh // 2
    img    = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)

    track_rgba = _hex_to_rgb(COLORS["track"]) + (255,)
    draw.rounded_rectangle([0, 0, sw-1, sh-1], radius=r, fill=track_rgba)

    if util > 0:
        fill_w = max(sh, int(sw * util))   # min width = height keeps ends round
        fill_rgba = _hex_to_rgb(color_hex) + (255,)
        draw.rounded_rectangle([0, 0, fill_w-1, sh-1], radius=r, fill=fill_rgba)

    return img.resize((BAR_W, BAR_H), Image.LANCZOS)


def _make_dot(color_hex: str, size: int = 10) -> Image.Image:
    """Small anti-aliased circle for legend."""
    s    = size * SCALE
    img  = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, s-1, s-1], fill=_hex_to_rgb(color_hex) + (255,))
    return img.resize((size, size), Image.LANCZOS)

# ── Tray icon ─────────────────────────────────────────────────────────────────

def make_icon(five_hour: Optional[float] = None,
              seven_day: Optional[float] = None) -> Image.Image:
    """64×64 tray icon. Outer arc = weekly, inner dot = 5h. 4× supersampled."""
    size = 64
    s    = size * SCALE   # 256
    img  = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if seven_day is None and five_hour is None:
        draw.ellipse([8*SCALE, 8*SCALE, (size-8)*SCALE, (size-8)*SCALE],
                     fill=(80, 80, 90, 255))
        return img.resize((size, size), Image.LANCZOS)

    sd  = seven_day  if seven_day  is not None else 0.0
    fh  = five_hour  if five_hour  is not None else 0.0

    pad, rw  = 3*SCALE, 10*SCALE
    bg_color = _hex_to_rgb(COLORS["bg"]) + (255,)
    track    = _hex_to_rgb(COLORS["track"]) + (255,)

    draw.ellipse([pad, pad, s-pad, s-pad], fill=bg_color)
    draw.arc([pad+SCALE, pad+SCALE, s-pad-SCALE, s-pad-SCALE],
             start=0, end=360, fill=track, width=rw)
    if sd > 0:
        draw.arc([pad+SCALE, pad+SCALE, s-pad-SCALE, s-pad-SCALE],
                 start=-90, end=-90 + int(360*sd),
                 fill=usage_rgb(sd) + (255,), width=rw)

    inner = pad + rw + 4*SCALE
    dot_color = usage_rgb(fh) + (255,) if fh > 0 else track
    draw.ellipse([inner, inner, s-inner, s-inner], fill=dot_color)

    return img.resize((size, size), Image.LANCZOS)

# ── Detail popup ──────────────────────────────────────────────────────────────

def _double_ring_section(parent, sd_util, sd_resets, fh_util, fh_resets):
    frame = tk.Frame(parent, bg=COLORS["bg"])
    frame.pack(pady=(2, 4))

    # Rings (PIL-rendered, displayed on Canvas)
    ring_img = _render_ring_image(sd_util, fh_util)
    cv = tk.Canvas(frame, width=RING_SIZE, height=RING_SIZE,
                   bg=COLORS["bg"], highlightthickness=0)
    cv.pack()
    cv._photo = ImageTk.PhotoImage(ring_img)   # prevent GC
    cv.create_image(0, 0, image=cv._photo, anchor="nw")

    # Centre text (ClearType via tkinter, layered over PIL rings)
    cx = RING_SIZE // 2
    sd_color = usage_hex(sd_util)
    cv.create_text(cx, cx - 14,
                   text=f"{int(sd_util*100)}%",
                   font=("Segoe UI", 26, "bold"), fill=sd_color)
    cv.create_text(cx, cx + 14,
                   text="7-Day",
                   font=("Segoe UI", 9), fill=COLORS["muted"])

    # Legend row
    legend = tk.Frame(frame, bg=COLORS["bg"])
    legend.pack(pady=(6, 0))

    for color, label in [
        (sd_color,         f"7d: {int(sd_util*100)}%"),
        (usage_hex(fh_util), f"5h: {int(fh_util*100)}%"),
    ]:
        lf = tk.Frame(legend, bg=COLORS["bg"])
        lf.pack(side="left", padx=10)

        dot_img = _make_dot(color, 8)
        dot_lbl = tk.Label(lf, bg=COLORS["bg"])
        dot_lbl._photo = ImageTk.PhotoImage(dot_img)
        dot_lbl.configure(image=dot_lbl._photo)
        dot_lbl.pack(side="left", padx=(0, 4))

        tk.Label(lf, text=label, font=("Segoe UI", 8),
                 bg=COLORS["bg"], fg=COLORS["muted"]).pack(side="left")

    # Reset times
    for rt in filter(None, [fmt_reset(sd_resets), fmt_reset(fh_resets)]):
        tk.Label(frame, text=rt, font=("Segoe UI", 8),
                 bg=COLORS["bg"], fg=COLORS["muted"]).pack()


def _bar_row(parent, label: str, util: float, resets_at: Optional[str]):
    """iOS-style metric card with pill progress bar."""
    card = tk.Frame(parent, bg=COLORS["bg2"], padx=14, pady=10)
    card.pack(fill="x", pady=(0, 8))

    color = usage_hex(util)
    pct   = int(util * 100)

    row = tk.Frame(card, bg=COLORS["bg2"])
    row.pack(fill="x", pady=(0, 6))
    tk.Label(row, text=label, font=("Segoe UI", 10),
             bg=COLORS["bg2"], fg=COLORS["text"]).pack(side="left")
    tk.Label(row, text=f"{pct}%", font=("Segoe UI", 10, "bold"),
             bg=COLORS["bg2"], fg=color).pack(side="right")

    bar_img = _render_pill_bar(util, color)
    bar_cv  = tk.Canvas(card, width=BAR_W, height=BAR_H,
                        bg=COLORS["bg2"], highlightthickness=0)
    bar_cv.pack()
    bar_cv._photo = ImageTk.PhotoImage(bar_img)
    bar_cv.create_image(0, 0, image=bar_cv._photo, anchor="nw")

    rt = fmt_reset(resets_at)
    if rt:
        tk.Label(card, text=rt, font=("Segoe UI", 8),
                 bg=COLORS["bg2"], fg=COLORS["muted"]).pack(anchor="w", pady=(4, 0))


EXTRA_BAR_KEYS = [
    ("seven_day_sonnet", "7-Day Sonnet"),
    ("seven_day_opus",   "7-Day Opus"),
]

HEADER_H    = 52
RING_H      = 248   # ring(180) + legend(38) + resets(30)
BAR_ROW_H   = 72
SEP_H       = 17
FOOTER_H    = 26
ERR_H       = 55
EMPTY_H     = 35
CARD_PAD    = 18    # content frame inset from card edge


def open_detail(root: tk.Tk, usage_data, last_error, last_updated):
    sd_data, fh_data, bar_rows = None, None, []

    if usage_data:
        sd_v = usage_data.get("seven_day")
        fh_v = usage_data.get("five_hour")
        if sd_v and "utilization" in sd_v:
            sd_data = (normalise(sd_v["utilization"]), sd_v.get("resets_at"))
        if fh_v and "utilization" in fh_v:
            fh_data = (normalise(fh_v["utilization"]), fh_v.get("resets_at"))
        for key, lbl in EXTRA_BAR_KEYS:
            v = usage_data.get(key)
            if v and isinstance(v, dict) and "utilization" in v:
                bar_rows.append((lbl, normalise(v["utilization"]), v.get("resets_at")))

    has_rings = sd_data or fh_data
    content_h = (
        HEADER_H
        + (RING_H if has_rings else 0)
        + (SEP_H  if has_rings and bar_rows else 0)
        + len(bar_rows) * BAR_ROW_H
        + (ERR_H   if last_error else 0)
        + (EMPTY_H if not has_rings and not bar_rows and not last_error else 0)
        + FOOTER_H
    )

    win = tk.Toplevel(root)
    win.overrideredirect(True)
    win.configure(bg=COLORS["bg"])
    win.attributes("-topmost", True)

    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"{POPUP_W}x{content_h}+{sw-POPUP_W-14}+{sh-content_h-52}")

    # Apply Windows 11 native rounded corners + drop shadow
    win.update_idletasks()
    _apply_dwm_style(win.winfo_id())

    # Content frame directly in window (no canvas background needed)
    content = tk.Frame(win, bg=COLORS["bg"])
    content.pack(fill="both", expand=True, padx=CARD_PAD, pady=CARD_PAD)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = tk.Frame(content, bg=COLORS["bg"])
    hdr.pack(fill="x", pady=(0, 8))
    tk.Label(hdr, text="Claude AI Usage", font=("Segoe UI", 13, "bold"),
             bg=COLORS["bg"], fg=COLORS["text"]).pack(side="left")
    close = tk.Label(hdr, text="✕", font=("Segoe UI", 11),
                     bg=COLORS["bg"], fg=COLORS["muted"], cursor="hand2")
    close.pack(side="right")
    close.bind("<Button-1>", lambda _: win.destroy())

    # ── Body ──────────────────────────────────────────────────────────────────
    if last_error:
        tk.Label(content, text=f"⚠  {last_error}",
                 font=("Segoe UI", 8), bg=COLORS["bg"], fg=COLORS["red"],
                 wraplength=POPUP_W - CARD_PAD*2 - 10,
                 justify="left").pack(anchor="w", pady=(0, 8))
    elif not has_rings and not bar_rows:
        tk.Label(content, text="Loading usage data…",
                 font=("Segoe UI", 10), bg=COLORS["bg"],
                 fg=COLORS["muted"]).pack(anchor="w", pady=8)
    else:
        sd_u, sd_r = sd_data if sd_data else (0.0, None)
        fh_u, fh_r = fh_data if fh_data else (0.0, None)
        _double_ring_section(content, sd_u, sd_r, fh_u, fh_r)

        if bar_rows:
            tk.Frame(content, bg=COLORS["separator"], height=1).pack(
                fill="x", pady=(4, 10))
            for lbl, util, ra in bar_rows:
                _bar_row(content, lbl, util, ra)

    # ── Footer ────────────────────────────────────────────────────────────────
    if last_updated:
        tk.Label(content, text=f"Updated {last_updated.strftime('%H:%M')}",
                 font=("Segoe UI", 8), bg=COLORS["bg"],
                 fg=COLORS["muted"]).pack(anchor="e", pady=(4, 8))

    # Focus + close-on-blur
    def _on_focus_out(event):
        focused = win.focus_get()
        if focused is None or not str(focused).startswith(str(win)):
            win.destroy()

    win.update_idletasks()
    win.focus_force()
    win.after(200, lambda: win.bind("<FocusOut>", _on_focus_out))
    win.bind("<Escape>", lambda _: win.destroy())

# ── App ───────────────────────────────────────────────────────────────────────

class App:
    def __init__(self):
        self.usage_data:   Optional[dict]     = None
        self.last_error:   Optional[str]      = None
        self.last_updated: Optional[datetime] = None
        self._lock  = threading.Lock()
        self._stop  = threading.Event()
        self._queue = queue.Queue()
        self.tray:  Optional[pystray.Icon] = None
        self.root:  Optional[tk.Tk]        = None

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
            if fh_v and "utilization" in fh_v: fh = normalise(fh_v["utilization"])
            if sd_v and "utilization" in sd_v: sd = normalise(sd_v["utilization"])
        if self.tray:
            self.tray.icon  = make_icon(fh, sd)
            self.tray.title = self._tooltip()

    def _tooltip(self) -> str:
        with self._lock:
            data, err = self.usage_data, self.last_error
        if err:      return "Claude Usage – Error"
        if not data: return "Claude Usage – Loading…"
        parts = []
        for key, label in [("seven_day", "7d"), ("five_hour", "5h")]:
            v = data.get(key)
            if v and "utilization" in v:
                parts.append(f"{label}: {int(normalise(v['utilization'])*100)}%")
        return ("Claude Usage — " + " | ".join(parts)) if parts else "Claude Usage"

    def _enqueue(self, fn):
        self._queue.put(fn)

    def _drain_queue(self):
        try:
            while True: self._queue.get_nowait()()
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
            pythonw = os.path.join(os.path.dirname(os.sys.executable), "pythonw.exe")
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

    def on_quit(self, *_):
        self._stop.set()
        if self.tray: self.tray.stop()
        if self.root: self.root.after(0, self.root.destroy)

    def run(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.after(150, self._drain_queue)

        menu = Menu(
            item("View Usage",         self.on_view,            default=True),
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
