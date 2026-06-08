const { makeTrayIcon } = require('../src/icon');

describe('makeTrayIcon', () => {
  test('returns a string starting with <svg', () => {
    const svg = makeTrayIcon(null, null);
    expect(typeof svg).toBe('string');
    expect(svg.trim().startsWith('<svg')).toBe(true);
  });

  test('contains outer arc when sdUtil provided', () => {
    const svg = makeTrayIcon(0.67, null);
    expect(svg).toContain('stroke="#FF9F0A"');
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
    expect(svg).toContain('fill="#34C759"');
  });

  test('uses neutral fill when fhUtil is null', () => {
    const svg = makeTrayIcon(null, null);
    expect(svg).toContain('fill="#3a3a48"');
  });
});
