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
