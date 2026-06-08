const zlib = require('zlib');
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

// PNG tray icon (Windows tray requires raster, not SVG)
const _crcTable = (() => {
  const t = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let j = 0; j < 8; j++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1;
    t[i] = c;
  }
  return t;
})();

function _crc32(buf) {
  let c = 0xFFFFFFFF;
  for (const b of buf) c = _crcTable[(c ^ b) & 0xFF] ^ (c >>> 8);
  return (c ^ 0xFFFFFFFF) >>> 0;
}

function _pngChunk(type, data) {
  const t = Buffer.from(type);
  const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
  const crc = Buffer.alloc(4); crc.writeUInt32BE(_crc32(Buffer.concat([t, data])));
  return Buffer.concat([len, t, data, crc]);
}

function _hexToRgb(hex) {
  const n = parseInt(hex.replace('#', ''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function makeIconPng(sdUtil, fhUtil) {
  const size = 64, cx = 32, cy = 32;
  const outerR = 24, trackW = 8, innerR = 10, discR = 30;

  const sdRgb = sdUtil != null ? _hexToRgb(usageColor(sdUtil, false)) : null;
  const fhRgb = fhUtil != null ? _hexToRgb(usageColor(fhUtil, false)) : [58, 58, 72];
  const track = [58, 58, 72], bg = [28, 28, 46];

  const rowSize = 1 + size * 4;
  const pixels = Buffer.alloc(rowSize * size, 0);

  for (let y = 0; y < size; y++) {
    pixels[y * rowSize] = 0;
    for (let x = 0; x < size; x++) {
      const dx = x - cx + 0.5, dy = y - cy + 0.5;
      const dist = Math.sqrt(dx * dx + dy * dy);
      const off = y * rowSize + 1 + x * 4;
      let r = 0, g = 0, b = 0, a = 0;

      if (dist <= discR)                           { [r, g, b] = bg;    a = 255; }
      const ri = outerR - trackW / 2, ro = outerR + trackW / 2;
      if (dist >= ri && dist <= ro)                { [r, g, b] = track; a = 255; }
      if (sdRgb && sdUtil > 0 && dist >= ri && dist <= ro) {
        let p = (Math.atan2(dy, dx) + Math.PI / 2) / (2 * Math.PI);
        if (p < 0) p += 1;
        if (p <= Math.min(sdUtil, 1))              { [r, g, b] = sdRgb; a = 255; }
      }
      if (dist <= innerR)                          { [r, g, b] = fhRgb; a = 255; }

      pixels[off] = r; pixels[off + 1] = g; pixels[off + 2] = b; pixels[off + 3] = a;
    }
  }

  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0); ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; ihdr[9] = 6;

  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    _pngChunk('IHDR', ihdr),
    _pngChunk('IDAT', zlib.deflateSync(pixels)),
    _pngChunk('IEND', Buffer.alloc(0)),
  ]);
}

module.exports = { makeTrayIcon, makeIconPng };
