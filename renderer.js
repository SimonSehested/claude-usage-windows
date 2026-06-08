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
