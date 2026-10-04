// Clock, play/pause, speed, scrubbing, status chips and the event line.
const el = id => document.getElementById(id);
let t = T0, playing = !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches), speed = 24, lastTs = null;

function clockText(h) {
  const d = Math.floor(h / 24) + 1, hh = Math.floor(h % 24), mm = Math.round((h % 1) * 60);
  return `Day ${d} \u00b7 ${String(hh).padStart(2, '0')}:${String(mm % 60).padStart(2, '0')}`;
}
function render() {
  const st = stateAt(t);
  update(st);
  if (!TS) return;
  el('clock').textContent = clockText(t);
  el('chipRO').className = 'chip' + (st.ro_on ? ' on' : ''); el('chipPump').className = 'chip' + (st.pump_on ? ' on' : '');
  el('scrub').value = Math.round(1000 * (t - T0) / Math.max(1e-9, T1 - T0));
  let ev = null; for (const e of DATA.events) { if (e[0] <= t) ev = e; else break; }
  el('evt').textContent = ev ? `${clockText(ev[0])} \u2014 ${ev[2]} (${ev[1]})` : 'No events yet';
}
function frame(ts) {
  if (playing && lastTs !== null) { t += (ts - lastTs) / 1000 * speed; if (t > T1) t = T0; }
  lastTs = ts; render(); requestAnimationFrame(frame);
}
function syncBtn() { el('play').textContent = playing ? 'Pause' : 'Play'; }

build();
if (!TS) {
  document.getElementById('mode').textContent = 'steady state at design flow';
  document.querySelector('.ctl').style.display = 'none'; document.querySelector('.chips').style.display = 'none';
  colourSel.addEventListener('change', render); render();
} else {
  document.getElementById('mode').textContent = `${Math.round((T1 - T0) / 24)}-day run`;
  DATA.events.forEach(e => { const m = document.createElement('i'); m.style.left = (100 * (e[0] - T0) / (T1 - T0)) + '%'; m.className = e[1] === 'Plant' ? 'warn' : ''; m.title = e[2]; el('ticks').appendChild(m); });
  el('play').onclick = () => { playing = !playing; syncBtn(); };
  el('back').onclick = () => { playing = false; t = Math.max(T0, t - 1); syncBtn(); };
  el('fwd').onclick = () => { playing = false; t = Math.min(T1, t + 1); syncBtn(); };
  el('speed').onchange = e => { speed = +e.target.value; };
  el('scrub').oninput = e => { t = T0 + (T1 - T0) * e.target.value / 1000; };
  colourSel.addEventListener('change', render);
  syncBtn(); requestAnimationFrame(frame);
}
