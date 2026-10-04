// Frame lookup. Levels and quality are interpolated between rows; flows and on/off flags hold per step.
const TS = DATA.mode === 'timeseries';
const T0 = TS ? DATA.frames.t_h[0] : 0;
const T1 = TS ? DATA.frames.t_h[DATA.frames.t_h.length - 1] : 0;

function stateAt(t) {
  if (!TS) {
    const q = {}; Object.keys(DATA.quality).forEach(k => q[k] = DATA.quality[k]);
    return {t, q, health: {}, ro_on: 1, pump_on: 1, lvl: {collection: .7, treated: .7, reuse: .7}, flows: null};
  }
  const F = DATA.frames, n = F.t_h.length, step = DATA.dt_h;
  const x = Math.min(n - 1, Math.max(0, (t - T0) / step)), i = Math.floor(x), j = Math.min(n - 1, i + 1), f = x - i;
  const L = a => a[i] + (a[j] - a[i]) * f;
  const q = {};
  for (const k in DATA.series) {
    const s = DATA.series[k];
    q[k] = {flow_lph: s.flow_lph[i], turbidity_ntu: L(s.turbidity_ntu), toc_mgl: L(s.toc_mgl), bacteria_log: L(s.bacteria_log)};
  }
  const health = {};
  for (const k in (DATA.health || {})) { const H = DATA.health[k], v = L(H.values); health[k] = {val: v, frac: v / H.limit, label: H.label, unit: H.unit, limit: H.limit, relative: H.relative}; }
  const P = DATA.plant, lvl = {
    collection: L(F.collection_l) / P.collection_l, treated: L(F.treated_l) / P.treated_l, reuse: L(F.reuse_l) / P.reuse_l,
  };
  const flows = {inflow: F.inflow_l[i] / step, delivered: F.delivered_l[i] / step,
                 transfer: (F.pump_on[i] && F.treated_l[i] > 1 && lvl.reuse < 0.999) ? q.uv.flow_lph : 0};
  return {t, i, q, health, ro_on: F.ro_on[i], pump_on: F.pump_on[i], lvl, flows,
          litres: {collection: L(F.collection_l), treated: L(F.treated_l), reuse: L(F.reuse_l)}};
}
