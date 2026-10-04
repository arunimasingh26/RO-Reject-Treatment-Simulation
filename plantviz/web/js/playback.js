// Clock, play/pause, speed, scrubbing, status chips, event flashes/log and the inspector.
const el = id => document.getElementById(id);
let t = T0, prevT = T0, playing = !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches), speed = 24, lastTs = null, selected = null, logN = -1;
const L2K = TS ? Object.fromEntries(Object.entries(DATA.labels || {}).map(([k, v]) => [v, k])) : {};
const evNode = e => { const k = L2K[e[1]]; return (k && byId[k]) ? k : (/overflow/i.test(e[2]) ? 'collection' : 'reuse'); };
const evKind = e => (e[1] === 'Plant' || /not fully|overflow|unmet|warn/i.test(e[2])) ? 'warn' : 'maint';

function clockText(h) {
  const d = Math.floor(h / 24) + 1, hh = Math.floor(h % 24), mm = Math.round((h % 1) * 60);
  return `Day ${d} \u00b7 ${String(hh).padStart(2, '0')}:${String(mm % 60).padStart(2, '0')}`;
}
function renderLog() {
  const done = DATA.events.filter(e => e[0] <= t);
  if (done.length === logN) return;
  logN = done.length;
  const last = done.slice(-6).reverse();
  el('log').innerHTML = last.length ? last.map(e => `<li class="${evKind(e) === 'warn' ? 'w' : ''}" data-t="${e[0]}"><small>${clockText(e[0])}</small>${e[2]} <small>${e[1]}</small></li>`).join('') : '<li class="empty">No events yet</li>';
}
function renderInspector(st) {
  if (!selected) return;
  const n = byId[selected], q = st.q[n.src], isStage = KEYS.includes(n.id) && n.id !== 'reject', pin = isStage ? st.q[PREV[n.id]] : null, h = st.health[n.id];
  const row = (lab, f) => `<tr><th>${lab}</th><td>${pin ? f(pin) + ' \u2192 ' : ''}${f(q)}</td></tr>`;
  el('insTitle').textContent = n.label;
  el('ins').className = '';
  el('ins').innerHTML = `<table><tr><th>Flow</th><td>${q.flow_lph.toFixed(0)} L/h</td></tr>` +
    row('Turbidity', x => x.turbidity_ntu.toFixed(2) + ' NTU') + row('Organics (TOC)', x => x.toc_mgl.toFixed(2) + ' mg/L') + row('Bacteria', x => x.bacteria_log.toFixed(2) + ' log') +
    (st.litres && st.litres[n.id] !== undefined ? `<tr><th>Stored</th><td>${Math.round(st.litres[n.id])} L (${Math.round(100 * st.lvl[n.id])}%)</td></tr>` : '') +
    (h ? `<tr><th>${h.label}</th><td>${fmtH(h)}</td></tr>` : '') + (pin ? '<tr><th></th><td class="empty">left of \u2192 is inlet, right is outlet</td></tr>' : '') + '</table>';
}
function render() {
  const st = stateAt(t);
  update(st);
  renderInspector(st);
  if (!TS) return;
  el('clock').textContent = clockText(t);
  el('chipRO').className = 'chip' + (st.ro_on ? ' on' : ''); el('chipPump').className = 'chip' + (st.pump_on ? ' on' : '');
  el('scrub').value = Math.round(1000 * (t - T0) / Math.max(1e-9, T1 - T0));
  renderLog();
}
function frame(ts) {
  if (playing && lastTs !== null) {
    t += (ts - lastTs) / 1000 * speed;
    if (t > T1) { t = T0; prevT = T0; }
    else if (t > prevT && t - prevT < 3) DATA.events.forEach(e => { if (e[0] > prevT && e[0] <= t) flashUnit(evNode(e), evKind(e)); });
  }
  prevT = t; lastTs = ts; render(); requestAnimationFrame(frame);
}
function syncBtn() {
  el('play').textContent = playing ? 'Pause' : 'Play';
  document.body.classList.toggle('paused', !playing);
  if (stage.pauseAnimations) { playing ? stage.unpauseAnimations() : stage.pauseAnimations(); }
}
function select(id) { selected = id; render(); }
stage.addEventListener('click', e => { const g = e.target.closest('.unit'); if (g) select(g.id.slice(2)); });
stage.addEventListener('keydown', e => { const g = e.target.closest && e.target.closest('.unit'); if (g && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); select(g.id.slice(2)); } });

build();
if (!TS) {
  document.getElementById('mode').textContent = 'steady state at design flow';
  document.querySelector('.ctl').style.display = 'none'; document.querySelector('.chips').style.display = 'none'; el('log').parentNode.style.display = 'none';
  colourSel.addEventListener('change', render); render();
} else {
  document.getElementById('mode').textContent = `${Math.round((T1 - T0) / 24)}-day run`;
  DATA.events.forEach(e => { const m = document.createElement('i'); m.style.left = (100 * (e[0] - T0) / (T1 - T0)) + '%'; m.className = evKind(e) === 'warn' ? 'warn' : ''; m.title = e[2]; el('ticks').appendChild(m); });
  el('log').addEventListener('click', ev => { const li = ev.target.closest('li[data-t]'); if (li) { t = prevT = +li.dataset.t; render(); } });
  el('play').onclick = () => { playing = !playing; syncBtn(); };
  el('back').onclick = () => { playing = false; t = prevT = Math.max(T0, t - 1); syncBtn(); };
  el('fwd').onclick = () => { playing = false; t = prevT = Math.min(T1, t + 1); syncBtn(); };
  el('speed').onchange = e => { speed = +e.target.value; };
  el('scrub').oninput = e => { t = prevT = T0 + (T1 - T0) * e.target.value / 1000; };
  colourSel.addEventListener('change', render);
  syncBtn(); requestAnimationFrame(frame);
}
