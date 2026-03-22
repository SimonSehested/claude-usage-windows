# Claude AI Usage Monitor for Windows

A Windows system tray app that shows your **claude.ai subscription usage** as a progress bar – so you always know how much of your session/weekly limit you've used, without opening the browser.

Inspired by the macOS apps shared on Reddit and [ClaudeUsageBar](https://www.claudeusagebar.com/).

![System tray icon showing usage ring]

---

## What it shows

| Metric | Description |
|---|---|
| **5-Hour Session** | How much of your current 5-hour message window you've used |
| **7-Day Limit** | How much of your weekly rolling limit you've used |
| **7-Day Sonnet** | Sonnet-specific weekly usage (Pro/Max plans) |
| **7-Day Opus** | Opus-specific weekly usage (if applicable) |

Colors: 🟢 green < 60% · 🟡 yellow < 85% · 🔴 red ≥ 85%

---

## Installation

**Requirements:** Python 3.8+ – download from [python.org](https://www.python.org/downloads/) (check *Add Python to PATH*)

```
1. Double-click  install.bat   ← installs Python dependencies
2. Double-click  run.bat       ← starts the app in the system tray
```

On first launch, a settings window opens automatically to enter your session key.

---

## Getting your session key

Your session key is a cookie from claude.ai that the app uses to fetch your usage data. It never leaves your computer.

**Step by step:**
1. Open [claude.ai](https://claude.ai) and make sure you're logged in
2. Press **F12** to open DevTools
3. Go to the **Network** tab, then press **F5** to reload
4. Find a request called **`usage`** and click it
5. In **Request Headers**, find the `Cookie:` header
6. Copy the value that starts with `sessionKey=sk-ant-sid01-…`
7. Paste it into the Settings window (the app strips the `sessionKey=` prefix automatically)

**Alternative (easier):**
1. Press F12 → **Application** tab → **Cookies** → `https://claude.ai`
2. Find the `sessionKey` row and copy the Value column

---

## Usage

| Action | Result |
|---|---|
| **Left-click** or double-click icon | Opens usage popup with progress bars |
| **Right-click** | Tray menu |
| Menu → **Refresh Now** | Forces an immediate update |
| Menu → **Settings…** | Update your session key |
| Menu → **Open Claude.ai** | Opens claude.ai in browser |

The app auto-refreshes every **5 minutes**.

---

## Run on startup

To launch automatically when Windows starts:

```
Double-click  add_to_startup.bat
```

To remove: delete `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ClaudeUsageMonitor.bat`

---

## Privacy & Security

- Your session key is stored in **Windows Credential Manager** (encrypted), not in a plain text file
- All requests go directly from your computer to `claude.ai` – no third-party servers
- No telemetry, no analytics, no data collection

---

## Notes

- This uses an **unofficial, undocumented** internal claude.ai API endpoint. It may break if Anthropic changes their API
- The session key expires periodically – if you see an error, get a fresh key from your browser
- Works on Free, Pro, and Max plans (available metrics vary by plan)

---

## Troubleshooting

| Problem | Fix |
|---|---|
| "No session key set" | Right-click tray → Settings → enter your key |
| "Session key is invalid or expired" | Get a fresh key from your browser (see above) |
| App doesn't appear in tray | Run `run.bat` again; check Task Manager for `pythonw.exe` |
| `ModuleNotFoundError` | Run `install.bat` first |
