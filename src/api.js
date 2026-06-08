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
