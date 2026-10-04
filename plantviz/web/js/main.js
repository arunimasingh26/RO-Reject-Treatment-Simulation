const stage = document.getElementById('stage');
const sel = document.getElementById('colourMode');
document.getElementById('mode').textContent = 'steady state at design flow';
const NS = 'http://www.w3.org/2000/svg';

function fmt(q) { return `${q.turbidity_ntu.toFixed(2)} NTU \u00b7 TOC ${q.toc_mgl.toFixed(1)} \u00b7 log ${q.bacteria_log.toFixed(1)}`; }

function draw() {
  const S = DATA.scales, mode = sel.value;
  let svg = '<defs>';
  const pipeD = {};
  PIPES.forEach(([a, b]) => { pipeD[a + '>' + b] = pipePath(byId[a], byId[b]); });
  Object.entries(pipeD).forEach(([k, d], i) => { svg += `<path id="p${i}" d="${d}"/>`; });
  svg += '</defs>';
  // pipes: steel casing, water core, flowing highlight
  Object.entries(pipeD).forEach(([k, d], i) => {
    const from = byId[k.split('>')[0]], q = DATA.quality[from.src], w = waterColour(q, S, mode);
    svg += `<path d="${d}" fill="none" stroke="${STEEL}" stroke-width="14" stroke-linejoin="round"/>` +
           `<path d="${d}" fill="none" stroke="${w}" stroke-width="9" stroke-linejoin="round"/>` +
           `<path class="flow" d="${d}"/>`;
    const sp = specks(q, S), dur = 5;
    for (let j = 0; j < sp.grey + sp.red; j++) {
      const red = j >= sp.grey, off = -(j * dur / 12);
      svg += `<circle r="${red ? 2.6 : 2}" fill="${red ? '#ff5a5f' : '#c9d3d6'}"><animateMotion dur="${dur}s" begin="${off}s" repeatCount="indefinite"><mpath href="#p${i}"/></animateMotion></circle>`;
    }
  });
  // units, labels, readouts
  NODES.forEach(n => {
    const q = DATA.quality[n.src], w = waterColour(q, S, mode);
    svg += `<g><title>${n.label}\nFlow ${q.flow_lph.toFixed(0)} L/h\n${fmt(q)}</title>${UNITS[n.type](n, w)}</g>`;
    svg += `<text class="lbl" x="${n.x}" y="${n.y - HALF_H - 14}">${n.label}</text>`;
    if (n.id !== 'ro') svg += `<text class="val" x="${n.x}" y="${n.y + HALF_H + 22}">${q.flow_lph.toFixed(0)} L/h</text>` +
                              `<text class="val" x="${n.x}" y="${n.y + HALF_H + 38}">${fmt(q)}</text>`;
  });
  svg += `<text class="val" x="100" y="${R1 + HALF_H + 22}">${DATA.plant.ro_feed_flow_lph} L/h feed</text>` +
         `<text class="val" x="100" y="${R1 + HALF_H + 38}">${Math.round(DATA.plant.ro_recovery * 100)}% recovery</text>`;
  // waste stubs
  Object.entries(WASTE).forEach(([k, lab]) => {
    const n = byId[k], v = DATA.waste_lph[k];
    if (v !== undefined) svg += `<text class="waste" x="${n.x}" y="${n.y + HALF_H + 54}" text-anchor="middle">\u2193 ${lab} ${v.toFixed(0)} L/h to drain</text>`;
  });
  // demand sink
  svg += `<path d="M${byId.reuse.x + byId.reuse.hw} ${R2}h50" stroke="${STEEL}" stroke-width="14"/><path d="M${byId.reuse.x + byId.reuse.hw} ${R2}h50" stroke="${waterColour(DATA.quality.uv, S, mode)}" stroke-width="9"/>` +
         `<text class="lbl" x="1150" y="${R2 + 5}">Reuse</text>`;
  // legend
  svg += `<g transform="translate(980,60)"><text class="lbl" style="text-anchor:start" x="0" y="0">Water colour</text>` +
         `<defs><linearGradient id="lg"><stop offset="0" stop-color="${css(CLEAN)}"/><stop offset="1" stop-color="${css(MURKY)}"/></linearGradient></defs>` +
         `<rect x="0" y="12" width="170" height="12" rx="6" fill="url(#lg)"/>` +
         `<text class="val" style="text-anchor:start" x="0" y="42">cleaner</text><text class="val" style="text-anchor:end" x="170" y="42">raw reject</text></g>`;
  stage.innerHTML = svg;
}
sel.addEventListener('change', draw);
draw();
