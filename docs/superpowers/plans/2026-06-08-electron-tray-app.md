# Claude Usage Monitor — Electron Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Python/tkinter tray app with a vanilla Electron app that shows Claude API usage in an iOS Liquid Glass-inspired popup, with automatic Windows light/dark mode support.

**Architecture:** Vanilla Electron — `main.js` (tray, window, API, theme) + `preload.js` (IPC bridge) + `renderer.*` (popup UI). Pure utility functions live in `src/api.js` and `src/icon.js` so they can be unit-tested with Jest independently of Electron.

**Tech Stack:** Electron 34, Node.js built-ins (`fs`, `https`), Jest 29 (dev), no bundler, no framework.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `package.json` | Create | Project config, dependencies, npm scripts |
| `.gitignore` | Update | Add `node_modules/`, `.superpowers/` |
| `src/api.js` | Create | `loadToken`, `fetchUsage`, `normalise`, `usageColor`, `formatReset` |
| `src/icon.js` | Create | `makeTrayIcon(sdUtil, fhUtil)` → SVG string |
| `tests/api.test.js` | Create | Unit tests for `src/api.js` |
| `tests/icon.test.js` | Create | Unit tests for `src/icon.js` |
| `preload.js` | Create | `contextBridge`: exposes `onData`, `reportHeight` to renderer |
| `renderer.html` | Create | Popup markup (no header/close button) |
| `renderer.css` | Create | CSS custom properties for light/dark themes |
| `renderer.js` | Create | DOM rendering logic (browser-side, no Node.js) |
| `main.js` | Create | Electron main: tray, BrowserWindow, API polling, theme detection |
| `run.bat` | Update | `npm start` |
| `install.bat` | Update | `npm install` |
| `add_to_startup.bat` | Update | `reg add` to `HKCU\...\Run` for Electron |
| `claude_usage.py` | Delete | Python app — replaced |
| `requirements.txt` | Delete | Python deps — replaced |

---

## Task 1: Scaffold — package.json, .gitignore, npm install

**Files:**
- Create: `package.json`
- Modify: `.gitignore`

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "claude-usage-monitor",
  "version": "1.0.0",
  "description": "Claude AI Usage Monitor for Windows",
  "main": "main.js",
  "scripts": {
    "start": "electron .",
    "test": "jest"
  },
  "dependencies": {
    "electron": "^34.0.0"
  },
  "devDependencies": {
    "jest": "^29.0.0"
  }
}
```

- [ ] **Step 2: Update `.gitignore`**

If `.gitignore` doesn't exist, create it. Append these lines:

```
node_modules/
.superpowers/
```

- [ ] **Step 3: Run `npm install`**

```
npm install
```

Expected: `node_modules/` folder created, `package-lock.json` created. No errors.

- [ ] **Step 4: Commit**

```bash
git add package.json .gitignore package-lock.json
git commit -m "feat: scaffold Electron project"
```

---

## Task 2: API utilities — TDD

**Files:**
- Create: `src/api.js`
- Create: `tests/api.test.js`

- [ ] **Step 1: Create `tests/api.test.js` (failing tests first)**

```javascript
const fs = require('fs');
const os = require('os');
const path = require('path');
const { normalise, usageColor, formatReset, loadToken } = require('../src/api');

describe('normalise', () => {
  test('passes through values already in [0,1]', () => {
    expect(normalise(0.67)).toBeCloseTo(0.67);
  });
  test('divides percentage values > 1 by 100', () => {
    expect(normalise(67)).toBeCloseTo(0.67);
  });
  test('handles string input', () => {
    expect(normalise('85')).toBeCloseTo(0.85);
  });
});

describe('usageColor', () => {
  test('returns green below 60%', () => {
    expect(usageColor(0.59, false)).toBe('#34C759');
    expect(usageColor(0.59, true)).toBe('#30D158');
  });
  test('returns yellow between 60% and 85%', () => {
    expect(usageColor(0.60, false)).toBe('#FF9F0A');
    expect(usageColor(0.84, true)).toBe('#FF9F0A');
  });
  test('returns red at 85% and above', () => {
    expect(usageColor(0.85, false)).toBe('#FF3B30');
    expect(usageColor(1.0, true)).toBe('#FF453A');
  });
});

describe('formatReset', () => {
  test('returns null for missing input', () => {
    expect(formatReset(null)).toBeNull();
    expect(formatReset(undefined)).toBeNull();
  });
  test('formats days and hours', () => {
    const future = new Date(Date.now() + (3 * 86400 + 14 * 3600) * 1000).toISOString();
    expect(formatReset(future)).toBe('om 3d 14t');
  });
  test('formats hours and minutes when less than a day', () => {
    const future = new Date(Date.now() + (2 * 3600 + 30 * 60) * 1000).toISOString();
    expect(formatReset(future)).toBe('om 2t 30m');
  });
  test('formats minutes when less than an hour', () => {
    const future = new Date(Date.now() + 45 * 60 * 1000).toISOString();
    expect(formatReset(future)).toBe('om 45m');
  });
  test('returns reset-soon string for past dates', () => {
    expect(formatReset(new Date(Date.now() - 1000).toISOString())).toBe('Nulstilles snart');
  });
});

describe('loadToken', () => {
  test('reads accessToken from credentials file', () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'claude-test-'));
    const creds = { claudeAiOauth: { accessToken: 'test-token-123' } };
    fs.writeFileSync(path.join(dir, '.credentials.json'), JSON.stringify(creds));
    const token = loadToken(path.join(dir, '.credentials.json'));
    expect(token).toBe('test-token-123');
    fs.rmSync(dir, { recursive: true });
  });
  test('throws when credentials file is missing', () => {
    expect(() => loadToken('/nonexistent/path/.credentials.json')).toThrow();
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

```
npm test
```

Expected: `Cannot find module '../src/api'`

- [ ] **Step 3: Create `src/api.js`**

Create the directory first: `mkdir src`

```javascript
const fs = require('fs');
const https = require('https');
const path = require('path');

const DEFAULT_CREDENTIALS_PATH = path.join(
  process.env.USERPROFILE || process.env.HOME || '',
  '.claude', '.credentials.json'
);

function loadToken(credentialsPath = DEFAULT_CREDENTIALS_PATH) {
  const raw = fs.readFileSync(credentialsPath, 'utf8');
  return JSON.parse(raw).claudeAiOauth.accessToken;
}

function normalise(v) {
  const n = parseFloat(v);
  return n > 1.0 ? n / 100.0 : n;
}

function usageColor(util, dark = false) {
  if (util < 0.60) return dark ? '#30D158' : '#34C759';
  if (util < 0.85) return '#FF9F0A';
  return dark ? '#FF453A' : '#FF3B30';
}

function formatReset(resetsAt) {
  if (!resetsAt) return null;
  const secs = Math.max(0, (new Date(resetsAt) - Date.now()) / 1000);
  if (secs <= 0) return 'Nulstilles snart';
  const d = Math.floor(secs / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (d) return `om ${d}d ${h}t`;
  if (h) return `om ${h}t ${m}m`;
  return `om ${m}m`;
}

function fetchUsage(credentialsPath = DEFAULT_CREDENTIALS_PATH) {
  return new Promise((resolve, reject) => {
    let token;
    try {
      token = loadToken(credentialsPath);
    } catch (e) {
      return reject(new Error('CREDENTIALS_MISSING'));
    }

    const options = {
      hostname: 'api.anthropic.com',
      path: '/api/oauth/usage',
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        'anthropic-beta': 'oauth-2025-04-20',
      },
    };

    const req = https.request(options, (res) => {
      let body = '';
      res.on('data', (chunk) => { body += chunk; });
      res.on('end', () => {
        if (res.statusCode === 401) return reject(new Error('TOKEN_EXPIRED'));
        if (res.statusCode !== 200) return reject(new Error(`HTTP_${res.statusCode}`));
        try {
          resolve(JSON.parse(body));
        } catch {
          reject(new Error('PARSE_ERROR'));
        }
      });
    });

    req.setTimeout(15000, () => {
      req.destroy();
      reject(new Error('TIMEOUT'));
    });
    req.on('error', reject);
    req.end();
  });
}

module.exports = { loadToken, normalise, usageColor, formatReset, fetchUsage };
```

- [ ] **Step 4: Run tests — verify they pass**

```
npm test
```

Expected: all tests pass, no failures.

- [ ] **Step 5: Commit**

```bash
git add src/api.js tests/api.test.js
git commit -m "feat: add API utility module with unit tests"
```

---

## Task 3: Tray icon generator — TDD

**Files:**
- Create: `src/icon.js`
- Create: `tests/icon.test.js`

- [ ] **Step 1: Create `tests/icon.test.js` (failing tests first)**

```javascript
const { makeTrayIcon } = require('../src/icon');

describe('makeTrayIcon', () => {
  test('returns a string starting with <svg', () => {
    const svg = makeTrayIcon(null, null);
    expect(typeof svg).toBe('string');
    expect(svg.trim().startsWith('<svg')).toBe(true);
  });

  test('contains outer arc when sdUtil provided', () => {
    const svg = makeTrayIcon(0.67, null);
    expect(svg).toContain('stroke="#34C759"');
  });

  test('uses red for high utilisation', () => {
    const svg = makeTrayIcon(0.90, null);
    expect(svg).toContain('stroke="#FF3B30"');
  });

  test('uses yellow for mid utilisation', () => {
    const svg = makeTrayIcon(0.70, null);
    expect(svg).toContain('stroke="#FF9F0A"');
  });

  test('inner circle colour reflects fhUtil', () => {
    const svg = makeTrayIcon(null, 0.45);
    expect(svg).toContain('fill="#FF9F0A"');
  });

  test('uses neutral fill when fhUtil is null', () => {
    const svg = makeTrayIcon(null, null);
    expect(svg).toContain('fill="#3a3a48"');
  });
});
```

- [ ] **Step 2: Run tests — verify they fail**

```
npm test -- tests/icon.test.js
```

Expected: `Cannot find module '../src/icon'`

- [ ] **Step 3: Create `src/icon.js`**

```javascript
const { usageColor } = require('./api');

function arcPath(cx, cy, r, util, strokeWidth, color) {
  if (!util || util <= 0) return '';
  const clamped = Math.min(util, 1);
  const circumference = 2 * Math.PI * r;
  const dash = (circumference * clamped).toFixed(2);
  const gap = (circumference * (1 - clamped)).toFixed(2);
  return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" stroke-dasharray="${dash} ${gap}" stroke-linecap="round" transform="rotate(-90 ${cx} ${cy})"/>`;
}

function makeTrayIcon(sdUtil, fhUtil) {
  const cx = 32, cy = 32;
  const outerR = 24, outerStroke = 8;
  const innerR = 10;

  const sdColor = sdUtil != null ? usageColor(sdUtil, false) : null;
  const fhColor = fhUtil != null ? usageColor(fhUtil, false) : '#3a3a48';

  return `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <circle cx="${cx}" cy="${cy}" r="30" fill="#1c1c2e"/>
  <circle cx="${cx}" cy="${cy}" r="${outerR}" fill="none" stroke="#3a3a48" stroke-width="${outerStroke}"/>
  ${sdUtil != null ? arcPath(cx, cy, outerR, sdUtil, outerStroke, sdColor) : ''}
  <circle cx="${cx}" cy="${cy}" r="${innerR}" fill="${fhColor}"/>
</svg>`;
}

module.exports = { makeTrayIcon };
```

- [ ] **Step 4: Run tests — verify they pass**

```
npm test
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/icon.js tests/icon.test.js
git commit -m "feat: add tray icon SVG generator with unit tests"
```

---

## Task 4: Renderer styles — renderer.css

**Files:**
- Create: `renderer.css`

- [ ] **Step 1: Create `renderer.css`**

```css
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --bg: #F2F2F7;
  --card: #FFFFFF;
  --track: #E5E5EA;
  --text: #1C1C1E;
  --muted: #8E8E93;
  --sep: #C6C6C8;
  --border: rgba(0, 0, 0, 0.08);
  --shadow: 0 16px 48px rgba(0, 0, 0, 0.14), 0 2px 8px rgba(0, 0, 0, 0.06);
}

[data-theme="dark"] {
  --bg: #1C1C1E;
  --card: rgba(255, 255, 255, 0.05);
  --track: rgba(255, 255, 255, 0.08);
  --text: rgba(255, 255, 255, 0.92);
  --muted: rgba(255, 255, 255, 0.40);
  --sep: rgba(255, 255, 255, 0.10);
  --border: rgba(255, 255, 255, 0.10);
  --shadow: 0 16px 48px rgba(0, 0, 0, 0.50), 0 2px 8px rgba(0, 0, 0, 0.30);
}

html, body {
  margin: 0;
  padding: 0;
  background: transparent;
  font-family: -apple-system, 'Segoe UI', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}

#app {
  background: var(--bg);
  border-radius: 20px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  padding: 16px;
  animation: fadein 120ms ease forwards;
}

@keyframes fadein {
  from { opacity: 0; }
  to   { opacity: 1; }
}

/* Ring section */
.ring-section {
  position: relative;
  display: flex;
  justify-content: center;
  margin-bottom: 10px;
}

.ring-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
}

.ring-pct {
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
}

.ring-label {
  font-size: 9px;
  font-weight: 500;
  color: var(--muted);
  letter-spacing: 0.6px;
  margin-top: 3px;
}

/* Legend */
.legend {
  display: flex;
  justify-content: center;
  gap: 18px;
  margin-bottom: 7px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.legend-text {
  font-size: 9px;
  color: var(--muted);
}

/* Reset times */
.reset-times {
  text-align: center;
  color: var(--muted);
  font-size: 8.5px;
  line-height: 1.7;
  margin-bottom: 6px;
}

.reset-times strong {
  color: var(--text);
  font-weight: 600;
}

/* Separator */
.separator {
  height: 1px;
  background: var(--sep);
  margin: 10px 0;
}

/* Bar rows */
.bars {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.bar-card {
  background: var(--card);
  border: 1px solid var(--sep);
  border-radius: 10px;
  padding: 9px 11px;
}

.bar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}

.bar-label {
  font-size: 10px;
  color: var(--text);
}

.bar-pct {
  font-size: 10px;
  font-weight: 600;
}

.bar-track {
  height: 5px;
  background: var(--track);
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
}

/* Footer */
.footer {
  text-align: right;
  font-size: 8px;
  color: var(--muted);
  margin-top: 10px;
}

/* States */
.loading {
  font-size: 11px;
  color: var(--muted);
  padding: 12px 0;
  text-align: center;
}

.error-msg {
  font-size: 10px;
  color: #FF3B30;
  padding: 8px 0;
  text-align: center;
  line-height: 1.5;
}
```

- [ ] **Step 2: Commit**

```bash
git add renderer.css
git commit -m "feat: add renderer styles with light/dark CSS custom properties"
```

---

## Task 5: Renderer logic — renderer.js

**Files:**
- Create: `renderer.js`

- [ ] **Step 1: Create `renderer.js`**

Note: This runs in the browser (renderer process). No `require()`. Mirrors `normalise`, `usageColor`, `formatReset` from `src/api.js` without Node deps.

```javascript
function normalise(v) {
  const n = parseFloat(v);
  return n > 1.0 ? n / 100.0 : n;
}

function usageColor(util, dark) {
  if (util < 0.60) return dark ? '#30D158' : '#34C759';
  if (util < 0.85) return '#FF9F0A';
  return dark ? '#FF453A' : '#FF3B30';
}

function formatReset(resetsAt) {
  if (!resetsAt) return null;
  const secs = Math.max(0, (new Date(resetsAt) - Date.now()) / 1000);
  if (secs <= 0) return 'Nulstilles snart';
  const d = Math.floor(secs / 86400);
  const h = Math.floor((secs % 86400) / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (d) return `om ${d}d ${h}t`;
  if (h) return `om ${h}t ${m}m`;
  return `om ${m}m`;
}

function makeRingSVG(sdUtil, fhUtil, dark) {
  const cx = 80, cy = 80;
  const outerR = 66, outerStroke = 12;
  const innerR = 40, innerStroke = 8;
  const track = dark ? 'rgba(255,255,255,0.08)' : '#E5E5EA';

  function arc(r, util, color, sw) {
    if (util == null || util <= 0) return '';
    const clamped = Math.min(util, 1);
    const c = 2 * Math.PI * r;
    const dash = (c * clamped).toFixed(2);
    const gap = (c * (1 - clamped)).toFixed(2);
    return `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="${color}"
      stroke-width="${sw}" stroke-dasharray="${dash} ${gap}" stroke-linecap="round"
      transform="rotate(-90 ${cx} ${cy})"/>`;
  }

  const sdColor = sdUtil != null ? usageColor(sdUtil, dark) : track;
  const fhColor = fhUtil != null ? usageColor(fhUtil, dark) : track;

  return `<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
    <circle cx="${cx}" cy="${cy}" r="${outerR}" fill="none" stroke="${track}" stroke-width="${outerStroke}"/>
    ${arc(outerR, sdUtil, sdColor, outerStroke)}
    <circle cx="${cx}" cy="${cy}" r="${innerR}" fill="none" stroke="${track}" stroke-width="${innerStroke}"/>
    ${arc(innerR, fhUtil, fhColor, innerStroke)}
  </svg>`;
}

const EXTRA_BARS = [
  ['seven_day_sonnet', '7-Day Sonnet'],
  ['seven_day_opus', '7-Day Opus'],
];

function render({ usageData, lastError, lastUpdated, dark }) {
  document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light');
  const app = document.getElementById('app');

  if (lastError) {
    app.innerHTML = `<div class="error-msg">⚠ ${lastError}</div>`;
    reportHeight();
    return;
  }

  if (!usageData) {
    app.innerHTML = `<div class="loading">Henter data…</div>`;
    reportHeight();
    return;
  }

  const sdRaw = usageData.seven_day?.utilization;
  const fhRaw = usageData.five_hour?.utilization;
  const sd = sdRaw != null ? normalise(sdRaw) : null;
  const fh = fhRaw != null ? normalise(fhRaw) : null;
  const sdResets = usageData.seven_day?.resets_at;
  const fhResets = usageData.five_hour?.resets_at;

  const sdColor = sd != null ? usageColor(sd, dark) : 'var(--muted)';
  const fhColor = fh != null ? usageColor(fh, dark) : 'var(--muted)';

  const sdReset = formatReset(sdResets);
  const fhReset = formatReset(fhResets);

  const barRows = EXTRA_BARS
    .filter(([key]) => usageData[key]?.utilization != null)
    .map(([key, label]) => {
      const u = normalise(usageData[key].utilization);
      const color = usageColor(u, dark);
      const pct = Math.round(u * 100);
      return `<div class="bar-card">
        <div class="bar-row">
          <span class="bar-label">${label}</span>
          <span class="bar-pct" style="color:${color}">${pct}%</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" style="width:${pct}%;background:${color}"></div>
        </div>
      </div>`;
    });

  const updatedStr = lastUpdated
    ? new Date(lastUpdated).toLocaleTimeString('da-DK', { hour: '2-digit', minute: '2-digit' })
    : '';

  app.innerHTML = `
    <div class="ring-section">
      ${makeRingSVG(sd, fh, dark)}
      <div class="ring-center">
        <div class="ring-pct" style="color:${sdColor}">${sd != null ? Math.round(sd * 100) + '%' : '—'}</div>
        <div class="ring-label">7-DAY</div>
      </div>
    </div>
    <div class="legend">
      <div class="legend-item">
        <span class="dot" style="background:${sdColor}"></span>
        <span class="legend-text">7-day <strong style="color:${sdColor}">${sd != null ? Math.round(sd * 100) + '%' : '—'}</strong></span>
      </div>
      <div class="legend-item">
        <span class="dot" style="background:${fhColor}"></span>
        <span class="legend-text">5-hour <strong style="color:${fhColor}">${fh != null ? Math.round(fh * 100) + '%' : '—'}</strong></span>
      </div>
    </div>
    <div class="reset-times">
      ${sdReset ? `<div>7-day nulstilles <strong>${sdReset}</strong></div>` : ''}
      ${fhReset ? `<div>5-hour nulstilles <strong>${fhReset}</strong></div>` : ''}
    </div>
    ${barRows.length ? `<div class="separator"></div><div class="bars">${barRows.join('')}</div>` : ''}
    ${updatedStr ? `<div class="footer">Opdateret ${updatedStr}</div>` : ''}
  `;

  reportHeight();
}

function reportHeight() {
  const h = document.getElementById('app').scrollHeight + 2;
  window.claude.reportHeight(h);
}

window.claude.onData(render);

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') window.claude.close();
});
```

- [ ] **Step 2: Commit**

```bash
git add renderer.js
git commit -m "feat: add renderer logic (ring SVG, bars, theme switching)"
```

---

## Task 6: Renderer markup — renderer.html

**Files:**
- Create: `renderer.html`

- [ ] **Step 1: Create `renderer.html`**

```html
<!DOCTYPE html>
<html lang="da">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self'; script-src 'self'; style-src 'self'">
  <link rel="stylesheet" href="renderer.css">
</head>
<body>
  <div id="app">
    <div class="loading">Henter data&hellip;</div>
  </div>
  <script src="renderer.js"></script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add renderer.html
git commit -m "feat: add renderer HTML"
```

---

## Task 7: IPC bridge — preload.js

**Files:**
- Create: `preload.js`

- [ ] **Step 1: Create `preload.js`**

```javascript
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('claude', {
  onData: (cb) => {
    ipcRenderer.on('usage-data', (_event, data) => cb(data));
  },
  reportHeight: (h) => {
    ipcRenderer.send('window-height', h);
  },
  close: () => {
    ipcRenderer.send('close-window');
  },
});
```

- [ ] **Step 2: Commit**

```bash
git add preload.js
git commit -m "feat: add preload IPC bridge"
```

---

## Task 8: Main process — main.js

**Files:**
- Create: `main.js`

- [ ] **Step 1: Create `main.js`**

```javascript
const {
  app, Tray, BrowserWindow, nativeImage, nativeTheme,
  ipcMain, screen, Menu, shell,
} = require('electron');
const path = require('path');
const { fetchUsage, normalise } = require('./src/api');
const { makeTrayIcon } = require('./src/icon');

const REFRESH_INTERVAL_MS = 5 * 60 * 1000;
const WIN_WIDTH = 280;
const WIN_MARGIN = 14;

let tray = null;
let win = null;
let usageData = null;
let lastError = null;
let lastUpdated = null;
let refreshTimer = null;
let isShowing = false;

// ── Icon ──────────────────────────────────────────────────────────────────────

function buildIcon(data) {
  let sd = null, fh = null;
  if (data) {
    if (data.seven_day?.utilization != null) sd = normalise(data.seven_day.utilization);
    if (data.five_hour?.utilization != null) fh = normalise(data.five_hour.utilization);
  }
  const svg = makeTrayIcon(sd, fh);
  return nativeImage.createFromDataURL(
    'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg)
  );
}

function buildTooltip(data) {
  if (!data) return 'Claude Usage — Loading…';
  const parts = [];
  if (data.seven_day?.utilization != null)
    parts.push(`7d: ${Math.round(normalise(data.seven_day.utilization) * 100)}%`);
  if (data.five_hour?.utilization != null)
    parts.push(`5h: ${Math.round(normalise(data.five_hour.utilization) * 100)}%`);
  return parts.length ? `Claude Usage — ${parts.join(' | ')}` : 'Claude Usage';
}

// ── Data ──────────────────────────────────────────────────────────────────────

async function refresh() {
  try {
    usageData = await fetchUsage();
    lastError = null;
    lastUpdated = new Date();
  } catch (e) {
    lastError = e.message === 'TOKEN_EXPIRED'
      ? 'Token udløbet — kør claude i en terminal'
      : e.message === 'CREDENTIALS_MISSING'
        ? 'Log ind: kør claude i en terminal'
        : 'Netværksfejl — prøv igen senere';
  }
  if (tray) {
    tray.setImage(buildIcon(usageData));
    tray.setToolTip(buildTooltip(usageData));
  }
}

function sendData() {
  if (!win) return;
  win.webContents.send('usage-data', {
    usageData,
    lastError,
    lastUpdated,
    dark: nativeTheme.shouldUseDarkColors,
  });
}

// ── Window ────────────────────────────────────────────────────────────────────

function getWinPosition(winHeight) {
  const { workArea } = screen.getPrimaryDisplay();
  const x = workArea.x + workArea.width - WIN_WIDTH - WIN_MARGIN;
  const y = workArea.y + workArea.height - winHeight - WIN_MARGIN;
  return { x, y };
}

function showPopup() {
  if (isShowing) return;
  isShowing = true;
  sendData();
}

function hidePopup() {
  if (!win) return;
  win.hide();
  isShowing = false;
}

// ── App ───────────────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  win = new BrowserWindow({
    width: WIN_WIDTH,
    height: 400,
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  win.loadFile('renderer.html');

  win.on('blur', () => {
    if (!isShowing) hidePopup();
  });

  // Renderer reports its content height after each render
  ipcMain.on('window-height', (_event, h) => {
    if (!win) return;
    const { x, y } = getWinPosition(h);
    win.setSize(WIN_WIDTH, h);
    win.setPosition(x, y);
    if (isShowing && !win.isVisible()) {
      win.show();
      win.focus();
      isShowing = false;
    }
  });

  // Escape key from renderer
  ipcMain.on('close-window', () => hidePopup());

  // Live theme updates
  nativeTheme.on('updated', () => {
    if (win?.isVisible()) sendData();
  });

  // Tray
  tray = new Tray(buildIcon(null));
  tray.setToolTip('Claude Usage — Loading…');

  const contextMenu = Menu.buildFromTemplate([
    { label: 'Opdater nu', click: () => refresh() },
    { type: 'separator' },
    { label: 'Afslut', click: () => app.quit() },
  ]);
  tray.setContextMenu(contextMenu);

  tray.on('click', async () => {
    if (win.isVisible()) {
      hidePopup();
      return;
    }
    await refresh();
    showPopup();
  });

  // Initial fetch
  refresh();
  refreshTimer = setInterval(refresh, REFRESH_INTERVAL_MS);
});

app.on('window-all-closed', (e) => e.preventDefault());
app.on('before-quit', () => {
  clearInterval(refreshTimer);
});
```

- [ ] **Step 2: Commit**

```bash
git add main.js
git commit -m "feat: add Electron main process (tray, window, API polling, theme)"
```

---

## Task 9: Update bat files, delete Python files

**Files:**
- Update: `run.bat`
- Update: `install.bat`
- Update: `add_to_startup.bat`
- Delete: `claude_usage.py`
- Delete: `requirements.txt`

- [ ] **Step 1: Update `run.bat`**

```batch
@echo off
cd /d "%~dp0"
npm start
```

- [ ] **Step 2: Update `install.bat`**

```batch
@echo off
cd /d "%~dp0"
echo Installing dependencies...
npm install
echo Done. Run run.bat to start the app.
pause
```

- [ ] **Step 3: Update `add_to_startup.bat`**

```batch
@echo off
cd /d "%~dp0"
set APPDIR=%~dp0
set ELECTRON=%APPDIR%node_modules\.bin\electron.cmd
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "ClaudeUsageMonitor" /t REG_SZ /d "\"%ELECTRON%\" \"%APPDIR%.\"" /f
echo Lagt til Windows-opstart.
pause
```

- [ ] **Step 4: Delete Python files**

```bash
git rm claude_usage.py requirements.txt
```

- [ ] **Step 5: Commit all**

```bash
git add run.bat install.bat add_to_startup.bat
git commit -m "feat: replace Python app with Electron — update bat files, delete Python"
```

---

## Task 10: Manual smoke test

No automated test can cover the Electron tray integration — do this by hand.

- [ ] **Step 1: Install and run**

```
npm install
npm start
```

Expected: app starts silently, tray icon appears in the bottom-right taskbar after the first API fetch completes (a few seconds).

- [ ] **Step 2: Test left-click**

Click the tray icon. Expected: popup appears in bottom-right corner with ring and data. Click away or press Escape. Expected: popup closes.

- [ ] **Step 3: Test data display**

Verify in the popup:
- Outer ring shows 7-day percentage in the correct colour (green/yellow/red)
- Inner ring shows 5-hour percentage
- Reset countdowns are visible ("7-day nulstilles om X")
- Bar rows for Sonnet/Opus appear if the API returns them
- Footer shows current time

- [ ] **Step 4: Test dark mode**

Go to Windows Settings → Personalisation → Colour → Dark mode. Expected: popup switches to dark theme immediately if it's open, or on next open.

Switch back to Light. Expected: popup switches back.

- [ ] **Step 5: Test error state**

Temporarily rename `~/.claude/.credentials.json` to `~/.claude/.credentials.json.bak`, then click the tray icon. Expected: popup shows the "Log ind" error message. Rename the file back.

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "chore: complete Electron tray app — Python removed, smoke test passed"
```
