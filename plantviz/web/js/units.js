// One drawing function per unit type. Each returns an SVG string centred on (x, y).
const STEEL = '#3b5866', GLASS = '#a9c7d2';
const body = (x, y, w, h, r = 8) => `<rect x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="${r}" fill="#0f2631" stroke="${STEEL}" stroke-width="2"/>`;

const UNITS = {
  tank: (n, w) => {
    const W = n.hw * 2, top = n.y - HALF_H, lvl = 0.7 * HALF_H * 2;
    return body(n.x, n.y, W, HALF_H * 2, 6) +
      `<rect x="${n.x - n.hw + 3}" y="${top + HALF_H * 2 - lvl}" width="${W - 6}" height="${lvl - 3}" rx="4" fill="${w}"/>` +
      `<path d="M${n.x - n.hw + 3} ${top + HALF_H * 2 - lvl}q${n.hw / 2} -5 ${n.hw} 0t${n.hw} 0" stroke="#e9fbff" stroke-opacity=".5" fill="none"/>`;
  },
  vessel: (n, w) => body(n.x, n.y, n.hw * 2, HALF_H * 2, 14) +
    `<rect x="${n.x - n.hw + 4}" y="${n.y - HALF_H + 4}" width="${n.hw * 2 - 8}" height="26" fill="${w}"/>` +
    `<rect x="${n.x - n.hw + 4}" y="${n.y - HALF_H + 30}" width="${n.hw * 2 - 8}" height="36" fill="#6b4f2a" opacity=".85"/>` +
    `<rect x="${n.x - n.hw + 4}" y="${n.y - HALF_H + 66}" width="${n.hw * 2 - 8}" height="30" fill="#c8b58a" opacity=".85"/>` +
    `<rect x="${n.x - n.hw + 4}" y="${n.y - HALF_H + 96}" width="${n.hw * 2 - 8}" height="30" fill="${w}" opacity=".7"/>`,
  carbon: (n, w) => body(n.x, n.y, n.hw * 2, HALF_H * 2, 14) +
    `<rect x="${n.x - n.hw + 4}" y="${n.y - HALF_H + 4}" width="${n.hw * 2 - 8}" height="22" fill="${w}"/>` +
    `<rect x="${n.x - n.hw + 4}" y="${n.y - HALF_H + 26}" width="${n.hw * 2 - 8}" height="102" fill="#1c2226" rx="3"/>` +
    [0, 1, 2, 3, 4].map(i => `<circle cx="${n.x - 20 + i * 10}" cy="${n.y - 30 + (i % 2) * 24 + i * 6}" r="3" fill="#39434a"/>`).join(''),
  cartridge: (n, w) => body(n.x, n.y, n.hw * 2, HALF_H * 2 - 10, 10) +
    `<rect x="${n.x - 14}" y="${n.y - HALF_H + 14}" width="28" height="${HALF_H * 2 - 38}" rx="14" fill="#dfe8ea" opacity=".9"/>` +
    Array.from({length: 7}, (_, i) => `<line x1="${n.x - 14}" x2="${n.x + 14}" y1="${n.y - HALF_H + 26 + i * 14}" y2="${n.y - HALF_H + 26 + i * 14}" stroke="#9fb4ba"/>`).join('') +
    `<rect x="${n.x - n.hw + 3}" y="${n.y + HALF_H - 24}" width="${n.hw * 2 - 6}" height="14" fill="${w}" rx="3"/>`,
  uf: (n, w) => body(n.x, n.y, n.hw * 2, HALF_H * 2, 14) +
    Array.from({length: 7}, (_, i) => `<line x1="${n.x - 24 + i * 8}" x2="${n.x - 24 + i * 8}" y1="${n.y - HALF_H + 14}" y2="${n.y + HALF_H - 14}" stroke="${GLASS}" stroke-width="3" stroke-linecap="round" opacity=".8"/>`).join('') +
    `<rect x="${n.x - n.hw + 4}" y="${n.y + HALF_H - 22}" width="${n.hw * 2 - 8}" height="14" fill="${w}" rx="3"/>`,
  uv: (n, w) => body(n.x, n.y, n.hw * 2, 56, 28) +
    `<rect x="${n.x - n.hw + 8}" y="${n.y - 9}" width="${n.hw * 2 - 16}" height="18" rx="9" fill="#c9a8ff" opacity=".95"/>` +
    `<rect x="${n.x - n.hw + 8}" y="${n.y - 9}" width="${n.hw * 2 - 16}" height="18" rx="9" fill="none" stroke="#e9d9ff" stroke-width="2" opacity=".8"/>` +
    `<rect x="${n.x - n.hw - 4}" y="${n.y - 22}" width="${n.hw * 2 + 8}" height="44" rx="22" fill="none" stroke="${w}" stroke-width="3" opacity=".7"/>`,
  ro: (n, w) => body(n.x, n.y, n.hw * 2, 70, 8) +
    Array.from({length: 5}, (_, i) => `<line x1="${n.x - 30 + i * 15}" x2="${n.x - 30 + i * 15}" y1="${n.y - 24}" y2="${n.y + 24}" stroke="#4aa3b8" stroke-width="3"/>`).join('') +
    `<rect x="${n.x - n.hw + 4}" y="${n.y + 24}" width="${n.hw * 2 - 8}" height="7" fill="${w}" rx="2"/>`,
};
