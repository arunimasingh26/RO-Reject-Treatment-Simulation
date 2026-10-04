// Quality -> colour and particle counts. All values are relative to the raw reject water.
const CLEAN = [95, 208, 232], MURKY = [138, 106, 54];
const clamp01 = x => Math.max(0, Math.min(1, x));
const mixRGB = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
const css = c => `rgb(${c[0]},${c[1]},${c[2]})`;

function fractions(q, S) {
  const i = S.inlet, f = S.bacteria_floor;
  return {
    turbidity: clamp01(q.turbidity_ntu / i.turbidity_ntu),
    toc: clamp01(q.toc_mgl / i.toc_mgl),
    bacteria: clamp01((q.bacteria_log - f) / (i.bacteria_log - f)),
  };
}
function murk(q, S, mode) {
  const f = fractions(q, S);
  const m = mode === 'composite' ? 0.5 * f.turbidity + 0.5 * f.toc : f[mode];
  return Math.pow(m, 1.3);  // contrast boost so small real changes stay visible
}
const waterColour = (q, S, mode) => css(mixRGB(CLEAN, MURKY, murk(q, S, mode)));
const specks = (q, S) => {
  const f = fractions(q, S);
  return {grey: Math.round(6 * f.turbidity), red: Math.round(6 * f.bacteria)};
};
