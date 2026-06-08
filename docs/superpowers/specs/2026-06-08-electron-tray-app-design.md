# Claude Usage Monitor — Electron Redesign

**Date:** 2026-06-08
**Status:** Approved

---

## Goal

Replace the buggy Python/tkinter/pystray app with a clean Electron app that has identical functionality, an Apple Liquid Glass-inspired visual style, and automatic Windows light/dark mode support.

---

## Architecture

Vanilla Electron — no bundler, no framework, no build step.

| File | Role |
|---|---|
| `main.js` | Electron main process: tray icon, BrowserWindow lifecycle, API calls, dark/light mode detection |
| `preload.js` | Secure bridge between main and renderer via `contextBridge` / `ipcRenderer` |
| `renderer.html` | Popup UI markup |
| `renderer.css` | Styles — two themes (light/dark), loaded dynamically |
| `package.json` | Electron dependency, start script |

Entry point: `electron .` (via `run.bat`).

---

## Visual Design

### Color palette

Follows Apple's iOS system colors, adapted for light and dark mode:

| Token | Light | Dark |
|---|---|---|
| Background | `#F2F2F7` | `#1C1C1E` |
| Card background | `#FFFFFF` | `rgba(255,255,255,0.05)` |
| Track (ring/bar empty) | `#E5E5EA` | `rgba(255,255,255,0.08)` |
| Primary text | `#1C1C1E` | `rgba(255,255,255,0.92)` |
| Secondary text | `#8E8E93` | `rgba(255,255,255,0.40)` |
| Separator | `#C6C6C8` | `rgba(255,255,255,0.10)` |
| Green (< 60%) | `#34C759` | `#30D158` |
| Yellow (< 85%) | `#FF9F0A` | `#FF9F0A` |
| Red (≥ 85%) | `#FF3B30` | `#FF453A` |

### Popup window

- Size: 280px wide, auto height
- Position: bottom-right corner, 14px from screen edge, above taskbar
- Chrome: `frame: false`, `transparent: true`, rounded corners via CSS (`border-radius: 20px`)
- Shadow: CSS `box-shadow` for depth
- Fade-in: opacity animates from 0 → 1 over ~120ms on open
- Dismiss: closes on window blur or Escape key

### Popup layout (top to bottom)

1. **Header** — "Claude AI Usage" (bold, 13px) + ✕ close button
2. **Separator** (1px)
3. **Double ring** (SVG, 160px diameter)
   - Outer arc: 7-day utilisation, coloured by threshold
   - Inner arc: 5-hour utilisation, coloured by threshold
   - Centre text: 7-day percentage (large) + "7-DAY" label (small, muted)
4. **Legend row** — two dot + label pairs: "7-day 67%" and "5-hour 32%"
5. **Reset times** — "7-day nulstilles om **3d 14t**" / "5-hour nulstilles om **3t 22m**" (small, centred)
6. **Separator** (1px, only if bar rows follow)
7. **Bar rows** (one card per metric, only rendered if API returns the field)
   - 7-Day Sonnet
   - 7-Day Opus
   - Each card: label + percentage on top row, pill progress bar below
8. **Footer** — "Opdateret HH:MM" (right-aligned, muted, 8px)

### Tray icon

- 64×64 icon generated in main process as an SVG string, converted to `nativeImage` via `nativeImage.createFromDataURL('data:image/svg+xml,...')`
- Outer arc: 7-day utilisation
- Inner filled circle: 5-hour utilisation colour
- Dark navy disc background for readability on any taskbar colour
- Tooltip: "Claude Usage — 7d: 67% | 5h: 32%"
- Redrawn on every data refresh

---

## Dark / Light Mode

`nativeTheme.shouldUseDarkColors` determines which theme is active at startup. The renderer receives the current theme via `contextBridge` and applies a `data-theme="dark"` attribute on `<html>`. CSS custom properties switch colour tokens accordingly.

`nativeTheme` emits a `updated` event when the user changes the Windows theme — main process re-sends the new value to the renderer via `ipcRenderer`, which updates `data-theme` live without restarting.

---

## Data Layer

### Credentials

Read from `%USERPROFILE%\.claude\.credentials.json` → `claudeAiOauth.accessToken`. No separate storage or manual setup required.

### API

```
GET https://api.anthropic.com/api/oauth/usage
Authorization: Bearer <token>
anthropic-beta: oauth-2025-04-20
```

Timeout: 15s. Response fields consumed:

| Field | Used for |
|---|---|
| `seven_day.utilization` | Outer ring + 7-day label |
| `seven_day.resets_at` | Reset countdown |
| `five_hour.utilization` | Inner ring + 5-hour label |
| `five_hour.resets_at` | Reset countdown |
| `seven_day_sonnet.utilization` | Sonnet bar row |
| `seven_day_opus.utilization` | Opus bar row |

### Refresh schedule

- Background poll every 5 minutes via `setInterval` in main process
- Left-click on tray icon triggers an immediate refresh before opening popup
- On 401: show "Token expired — run `claude` in a terminal" in popup
- On network error / timeout: show error message in popup, retain last known data in tray icon

---

## Startup & Packaging

- `run.bat`: runs `electron .`
- `add_to_startup.bat`: adds Electron entry to `HKCU\...\Run` registry key (replaces Python version)
- `install.bat`: runs `npm install`
- `.gitignore`: add `node_modules/` and `.superpowers/`

---

## Files Removed / Updated

| File | Action | Reason |
|---|---|---|
| `claude_usage.py` | Deleted | Replaced by Electron app |
| `requirements.txt` | Deleted | Python deps no longer needed |
| `install.bat` | Updated | Now runs `npm install` instead of pip |
| `run.bat` | Updated | Now runs `electron .` |
| `add_to_startup.bat` | Updated | Points to Electron instead of pythonw |
