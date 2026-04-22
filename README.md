# Claude AI Usage Monitor for Windows

A Windows system tray app that shows your **claude.ai subscription usage** as a progress bar – so you always know how much of your session/weekly limit you've used, without opening the browser.

Inspired by the macOS apps shared on Reddit and [ClaudeUsageBar](https://www.claudeusagebar.com/).

---

## What it shows

| Metric | Description |
|---|---|
| **5-Hour Session** | How much of your current 5-hour message window you've used |
| **7-Day Limit** | How much of your weekly rolling limit you've used |
| **7-Day Sonnet** | Sonnet-specific weekly usage (Pro/Max plans) |
| **7-Day Opus** | Opus-specific weekly usage (if applicable) |

Colors: 🟢 green < 60% · 🟠 amber < 85% · 🔴 red ≥ 85%

The tray icon is **invisible until data has loaded** – it appears automatically once the first fetch completes.

---

## Requirements

- **Claude Code** installed and logged in (`claude` CLI)
- **Python 3.8+** (Miniforge/Anaconda/python.org)

No session key or manual setup required. The app reads credentials directly from Claude Code's login (`~/.claude/.credentials.json`).

---

## Installation

```
1. Double-click  install.bat   ← installs Python dependencies
2. Double-click  run.bat       ← starts the app in the system tray
```

---

## Usage

| Action | Result |
|---|---|
| **Left-click** icon | Fetches fresh data and opens usage popup |
| **Right-click** | Tray menu |
| Menu → **Refresh Now** | Forces an immediate background update |
| Menu → **Open Claude.ai** | Opens claude.ai in browser |

The app also auto-refreshes every **5 minutes** in the background.

---

## Run on startup

To launch automatically when Windows starts:

```
Double-click  add_to_startup.bat
```

To remove: delete `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ClaudeUsageMonitor.bat`

Alternatively, right-click the tray icon → **Start with Windows**.

---

## Privacy & Security

- Credentials are read from Claude Code's local login file – nothing is stored separately
- All requests go directly from your computer to `api.anthropic.com` – no third-party servers
- No telemetry, no analytics, no data collection

---

## Notes

- Requires an active Claude Code login. If the token expires, run `claude` in a terminal and log in again
- Works on Pro and Max plans (available metrics vary by plan)
- Uses the same OAuth token as Claude Code – if Claude Code works, this works

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Icon never appears | Make sure you're logged in: run `claude` in a terminal |
| "Token expired" error | Run `claude` in a terminal to refresh the login |
| App doesn't appear in tray | Run `run.bat` again; check Task Manager for `pythonw.exe` |
| `ModuleNotFoundError` | Run `install.bat` first |
