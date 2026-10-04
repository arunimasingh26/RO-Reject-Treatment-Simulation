// Builds the SVG once, then update() changes only colours, levels, flow and text.
const stage = document.getElementById('stage');
const colourSel = document.getElementById('colourMode');
const S = DATA.scales, MAXP = 12;
const $ = id => stage.querySelector('#' + id);
const fmtQ = q => `${q.turbidity_ntu.toFixed(2)} NTU \u00b7 TOC ${q.toc_mgl.toFixed(1)} \u00b7 log ${q.bacteria_log.toFixed(1)}`;
const TANK_KEY = {collection: 'collection', treated: 'treated', reuse: 'reuse'};
let refs = {};

function build() {
  let svg = '<defs>';
  PIPES.forEach(([a, b], i) => { svg += `<path id="p${i}" d="${pipePath(byId[a], byId[b])}"/>`; });
  svg += `<linearGradient id="lg"><stop offset="0" stop-color="${css(CLEAN)}"/><stop offset="1" stop-color="${css(MURKY)}"/></linearGradient></defs>`;
  PIPES.forEach(([a, b], i) => {
    const d = pipePath(byId[a], byId[b]);
    svg += `<path d="${d}" fill="none" stroke="${STEEL}" stroke-width="14" stroke-linejoin="round"/>` +
           `<path id="core${i}" d="${d}" fill="none" stroke-width="9" stroke-linejoin="round"/><path id="flow${i}" class="flow" d="${d}"/>`;
    for (let j = 0; j < MAXP; j++) {
      const red = j >= MAXP / 2, off = -(j * 5 / MAXP);
      svg += `<circle id="pt${i}_${j}" r="${red ? 2.6 : 2}" fill="${red ? '#ff5a5f' : '#c9d3d6'}"><animateMotion dur="5s" begin="${off}s" repeatCount="indefinite"><mpath href="#p${i}"/></animateMotion></circle>`;
    }
  });
  const re = byId.reuse, sd = `M${re.x + re.hw} ${R2}h50`;
  svg += `<path d="${sd}" stroke="${STEEL}" stroke-width="14"/><path id="coreS" d="${sd}" stroke-width="9"/><path id="flowS" class="flow" d="${sd}"/>` +
         `<text class="lbl" x="1150" y="${R2 + 5}">Demand</text>`;
  NODES.forEach(n => {
    svg += `<rect class="halo" id="h-${n.id}" x="${n.x - n.hw - 10}" y="${n.y - HALF_H - 10}" width="${n.hw * 2 + 20}" height="${HALF_H * 2 + 20}" rx="14"/>` +
           `<g id="u-${n.id}" class="unit" tabindex="0" role="button" aria-label="Inspect ${n.label}"><title id="ti-${n.id}"></title>${UNITS[n.type](n, '#888')}` +
           (n.id === 'equalisation' ? `<rect id="sludge" x="${n.x - n.hw + 3}" width="${n.hw * 2 - 6}" rx="3" fill="#5b4526"/>` : '') + `</g>` +
           `<text class="lbl" x="${n.x}" y="${n.y - HALF_H - 14}">${n.label}</text>` +
           `<text class="val" id="a-${n.id}" x="${n.x}" y="${n.y + HALF_H + 22}"></text><text class="val" id="b-${n.id}" x="${n.x}" y="${n.y + HALF_H + 38}"></text>` +
           (TS && DATA.health[n.id] ? `<rect x="${n.x - 36}" y="${n.y + HALF_H + 46}" width="72" height="5" rx="2.5" fill="#1a2b34"/><rect id="hb-${n.id}" x="${n.x - 36}" y="${n.y + HALF_H + 46}" width="0" height="5" rx="2.5"/>` : '');
  });
  Object.entries(WASTE).forEach(([k, lab]) => {
    svg += `<text class="waste" id="ws-${k}" x="${byId[k].x}" y="${byId[k].y + HALF_H + 68}" text-anchor="middle"></text>`;
  });
  svg += `<g transform="translate(980,60)"><text class="lbl" style="text-anchor:start" x="0" y="0">Water colour</text>` +
         `<rect x="0" y="12" width="170" height="12" rx="6" fill="url(#lg)"/>` +
         `<text class="val" style="text-anchor:start" x="0" y="42">cleaner</text><text class="val" style="text-anchor:end" x="170" y="42">raw reject</text></g>`;
  stage.innerHTML = svg;
  refs.last = {};
}

function setFlow(el, lph, key) {
  const on = lph > 1, dur = on ? Math.max(0.4, Math.min(4, 1.2 * (DATA.plant.treatment_flow_lph / lph))).toFixed(1) : 0;
  const k = on ? dur : 'off';
  if (refs.last[key] === k) return;
  refs.last[key] = k;
  el.style.display = on ? '' : 'none';
  if (on) el.style.animationDuration = dur + 's';
}

function update(st) {
  const mode = colourSel.value, q = st.q;
  const W = key => waterColour(q[key], S, mode);
  NODES.forEach(n => {
    const g = $('u-' + n.id), w = W(n.src), qq = q[n.src];
    g.querySelectorAll('.wt').forEach(e => e.setAttribute('fill', w));
    g.querySelectorAll('.wts').forEach(e => e.setAttribute('stroke', w));
    if (n.type === 'tank' && TANK_KEY[n.id]) {
      const fr = Math.max(0, Math.min(1, st.lvl[n.id])), H2 = HALF_H * 2, lv = fr * H2;
      const r = g.querySelector('.tk'); r.setAttribute('y', n.y + HALF_H - lv); r.setAttribute('height', Math.max(0, lv - 3));
      g.querySelector('.surf').setAttribute('transform', `translate(0,${(0.7 - fr) * H2})`);
    }
    const a = $('a-' + n.id), b = $('b-' + n.id);
    healthFx(n, g, st);
    if (n.id === 'ro') { a.textContent = st.ro_on ? 'running' : 'off'; b.textContent = `${Math.round(DATA.plant.ro_recovery * 100)}% recovery`; return; }
    const vol = st.litres && TANK_KEY[n.id] ? `${Math.round(st.litres[n.id])} L \u00b7 ` : '';
    a.textContent = TANK_KEY[n.id] && st.litres ? `${vol}${Math.round(100 * st.lvl[n.id])}%` : `${qq.flow_lph.toFixed(0)} L/h`;
    b.textContent = fmtQ(qq);
    const h = st.health[n.id];
    $('ti-' + n.id).textContent = `${n.label}\nFlow ${qq.flow_lph.toFixed(0)} L/h\n${fmtQ(qq)}` + (h ? `\n${h.label}: ${fmtH(h)}` : '');
  });
  PIPES.forEach(([a, b], i) => {
    const from = byId[a], w = W(from.src);
    let lph = q[from.src].flow_lph;
    if (st.flows) lph = i === 0 ? st.flows.inflow : (b === 'reuse' ? st.flows.transfer : lph);
    $('core' + i).setAttribute('stroke', w);
    setFlow($('flow' + i), lph, 'f' + i);
    const sp = specks(q[from.src], S);
    for (let j = 0; j < MAXP; j++) {
      const red = j >= MAXP / 2, c = red ? sp.red : sp.grey;
      $(`pt${i}_${j}`).setAttribute('opacity', (lph > 1 && (j % (MAXP / 2)) < c) ? 1 : 0);
    }
  });
  const dem = st.flows ? st.flows.delivered : q.uv.flow_lph;
  $('coreS').setAttribute('stroke', W('uv')); setFlow($('flowS'), dem, 'fS');
  Object.keys(WASTE).forEach(k => {
    const v = st.flows ? Math.max(0, (q[PREV[k]].flow_lph - q[k].flow_lph)) : DATA.waste_lph[k];
    $('ws-' + k).textContent = v > 0.5 ? `\u2193 ${WASTE[k]} ${v.toFixed(0)} L/h to drain` : '';
  });
}
const KEYS = Object.keys(TS ? DATA.series : DATA.quality);
const PREV = Object.fromEntries(KEYS.map((k, i) => [k, KEYS[i - 1]]));

const lerpC = (a, b, t) => css(mixRGB(a, b, clamp01(t)));
const fmtH = h => h.relative ? `${h.val.toFixed(1)} ${h.unit} (${Math.round(100 * h.frac)}% of run peak)` : `${h.val.toFixed(h.unit === 'h' ? 0 : 2)} / ${h.limit} ${h.unit} (${Math.round(100 * h.frac)}% of limit)`;
function healthFx(n, g, st) {
  const h = st.health[n.id]; if (!h) return;
  const f = clamp01(h.frac), set = (sel, attr, v) => g.querySelectorAll(sel).forEach(e => e.setAttribute(attr, v));
  if (n.id === 'mmf') set('.hl', 'fill', lerpC([200, 181, 138], [84, 58, 28], f));
  if (n.id === 'carbon') set('.hl', 'fill', lerpC([28, 34, 38], [100, 112, 120], f));
  if (n.id === 'cartridge_5um' || n.id === 'candle_05um') set('.hl', 'fill', lerpC([223, 232, 234], [122, 90, 50], f));
  if (n.id === 'uf') set('.hl', 'stroke', lerpC([169, 199, 210], [140, 100, 60], f));
  if (n.id === 'uv') set('.hl', 'opacity', st.pump_on ? 1 - 0.55 * f : 0.18);
  if (n.id === 'equalisation') { const hh = 22 * f, r = $('sludge'); r.setAttribute('height', hh); r.setAttribute('y', n.y + HALF_H - 3 - hh); }
  const b = $('hb-' + n.id);
  b.setAttribute('width', 72 * f); b.setAttribute('fill', f < 0.6 ? '#5fd09a' : f < 0.85 ? '#f0a93b' : '#ff6b6b');
}
function flashUnit(id, kind) {
  const e = $('h-' + id); if (!e) return;
  e.style.stroke = kind === 'warn' ? '#f0a93b' : '#7be0a0'; e.classList.remove('go'); void e.getBoundingClientRect(); e.classList.add('go');
}
