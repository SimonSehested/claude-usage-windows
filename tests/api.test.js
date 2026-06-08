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
    const result = formatReset(future);
    expect(result).toMatch(/^om 3d (13|14)t$/);
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
