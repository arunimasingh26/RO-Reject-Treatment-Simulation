// The floor plan. Change positions here only; rendering reads from this file.
const R1 = 150, R2 = 410;
const NODES = [
  {id: 'ro', type: 'ro', x: 100, y: R1, hw: 48, label: 'Dialysis RO', src: 'reject'},
  {id: 'collection', type: 'tank', x: 290, y: R1, hw: 50, label: 'Collection tank', src: 'reject'},
  {id: 'equalisation', type: 'tank', x: 480, y: R1, hw: 50, label: 'Equalisation tank', src: 'equalisation'},
  {id: 'mmf', type: 'vessel', x: 670, y: R1, hw: 32, label: 'Multimedia filter', src: 'mmf'},
  {id: 'carbon', type: 'carbon', x: 850, y: R1, hw: 36, label: 'ACF + GAC carbon', src: 'carbon'},
  {id: 'cartridge_5um', type: 'cartridge', x: 100, y: R2, hw: 26, label: '5 \u00b5m cartridge', src: 'cartridge_5um'},
  {id: 'candle_05um', type: 'cartridge', x: 280, y: R2, hw: 26, label: '0.5 \u00b5m candle', src: 'candle_05um'},
  {id: 'uf', type: 'uf', x: 460, y: R2, hw: 36, label: 'UF membrane', src: 'uf'},
  {id: 'uv', type: 'uv', x: 650, y: R2, hw: 44, label: 'UV disinfection', src: 'uv'},
  {id: 'treated', type: 'tank', x: 840, y: R2, hw: 50, label: 'Treated tank', src: 'uv'},
  {id: 'reuse', type: 'tank', x: 1030, y: R2, hw: 50, label: 'Reuse tank', src: 'uv'},
];
const HALF_H = 66;
// Pipes: [from, to]; the carbon -> cartridge pipe is a serpentine return, drawn as an elbow.
const PIPES = NODES.slice(0, -1).map((n, i) => [n.id, NODES[i + 1].id]);
const WASTE = {mmf: 'Backwash', uf: 'UF concentrate'};  // stage key -> label of its waste stub
const byId = Object.fromEntries(NODES.map(n => [n.id, n]));

function pipePath(a, b) {
  if (a.y === b.y) return `M${a.x + a.hw} ${a.y}L${b.x - b.hw} ${b.y}`;
  const ym = a.y + HALF_H + 80;
  return `M${a.x} ${a.y + HALF_H}L${a.x} ${ym}L${b.x} ${ym}L${b.x} ${b.y - HALF_H}`;
}
