const {
  app, Tray, BrowserWindow, nativeImage, nativeTheme,
  ipcMain, screen, Menu,
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

  // Escape key from renderer
  ipcMain.on('close-window', () => hidePopup());

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
