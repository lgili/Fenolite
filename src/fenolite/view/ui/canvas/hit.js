// ================================================================== hit test (2D)
function segDist(px, py, x1, y1, x2, y2) { const dx = x2 - x1, dy = y2 - y1, L = dx * dx + dy * dy; let t = L ? ((px - x1) * dx + (py - y1) * dy) / L : 0;
  t = Math.max(0, Math.min(1, t)); return Math.hypot(px - x1 - t * dx, py - y1 - t * dy); }
function inRing(px, py, r) { let c = false; for (let i = 0, j = r.length - 2; i < r.length; j = i, i += 2) {
  const xi = r[i], yi = r[i + 1], xj = r[j], yj = r[j + 1]; if (((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) c = !c; } return c; }
function hitPrim(pr, x, y, tol) { const d = pr[2]; switch (pr[1]) {
  case "s": return segDist(x, y, d[0], d[1], d[2], d[3]) <= d[4] / 2 + tol;
  case "c": return Math.hypot(x - d[0], y - d[1]) <= d[2] + tol;
  case "l": for (let i = 1; i + 3 < d.length; i += 2) if (segDist(x, y, d[i], d[i + 1], d[i + 2], d[i + 3]) <= d[0] / 2 + tol) return true; return d.length === 3 && Math.hypot(x - d[1], y - d[2]) <= d[0] / 2 + tol;
  case "a": { const a = pr[6]; if (!a) return segDist(x, y, d[0], d[1], d[4], d[5]) <= d[6] / 2 + tol; if (Math.abs(Math.hypot(x - a.cx, y - a.cy) - a.r) > d[6] / 2 + tol) return false;
    const T = 2 * Math.PI, t = Math.atan2(y - a.cy, x - a.cx); let span = ((a.a3 - a.a1) % T + T) % T, at = ((t - a.a1) % T + T) % T; if (a.ccw) { span = T - span; at = ((a.a1 - t) % T + T) % T; } return at <= span; }
  case "p": case "h": { let n = 0; for (const r of d) if (inRing(x, y, r)) n++; return n % 2 === 1; }
  case "o": for (const r of d) for (let i = 0; i < r.length; i += 2) { const j = (i + 2) % r.length; if (segDist(x, y, r[i], r[i + 1], r[j], r[j + 1]) <= tol) return true; } return false; }
  return false; }
function pickLayers() {
  const layers = order().map(e => e[0]).reverse().filter(l => l.id !== "View.Drill" && l.id !== "View.Outline");
  const outl = l => l.id === "View.ZoneOutline" || l.id === "View.ZoneEdge";
  layers.sort((a, b) => outl(a) - outl(b));   // copper before zone outlines
  return layers;
}
// c0245 (decision 7): a uniform grid per layer holds the index of each primitive in the cells its box covers,
// so a click tests only the primitives near it, in the order the full scan used (the same result)
const PICK_CELL = 2;   // millimetres
let PICK_GRID = new Map(), PICK_OF = null;
function pickGrid(lid) {
  if (PICK_OF !== byLayer) { PICK_GRID = new Map(); PICK_OF = byLayer; }
  let g = PICK_GRID.get(lid); if (g) return g; g = new Map();
  (byLayer.get(lid) || []).forEach(([, b], i) => {
    const i0 = Math.floor(b[0] / PICK_CELL), i1 = Math.floor(b[2] / PICK_CELL), j0 = Math.floor(b[1] / PICK_CELL), j1 = Math.floor(b[3] / PICK_CELL);
    if ((i1 - i0 + 1) * (j1 - j0 + 1) > 40000) { (g.big || (g.big = [])).push(i); return; }   // a huge box: tested on every click
    for (let a = i0; a <= i1; a++) for (let c = j0; c <= j1; c++) { const k = a * 1048576 + c; let cell = g.get(k); if (!cell) { cell = []; g.set(k, cell); } cell.push(i); } });
  PICK_GRID.set(lid, g); return g;
}
function pick(X, Y) {
  const [x, y] = s2w(X, Y), tol = 3 / view.s;
  for (const l of pickLayers()) {
    const list = byLayer.get(l.id) || []; if (!list.length) continue;
    const g = pickGrid(l.id), seen = new Set(g.big || []);
    for (let a = Math.floor((x - tol) / PICK_CELL); a <= Math.floor((x + tol) / PICK_CELL); a++)
      for (let c = Math.floor((y - tol) / PICK_CELL); c <= Math.floor((y + tol) / PICK_CELL); c++) for (const i of g.get(a * 1048576 + c) || []) seen.add(i);
    for (const i of [...seen].sort((p, q) => p - q)) { const [pr, b] = list[i]; if (x < b[0] - tol || x > b[2] + tol || y < b[1] - tol || y > b[3] + tol) continue;
      if (hitPrim(pr, x, y, tol)) return { layer: l, pr }; } }
  return null;
}
function pickScan(X, Y) {   // the full scan the grid replaces, kept for the test that compares them
  const [x, y] = s2w(X, Y), tol = 3 / view.s;
  for (const l of pickLayers()) for (const [pr, b] of byLayer.get(l.id) || []) { if (x < b[0] - tol || x > b[2] + tol || y < b[1] - tol || y > b[3] + tol) continue;
    if (hitPrim(pr, x, y, tol)) return { layer: l, pr }; }
  return null;
}
function showInfo(html, prov) {   // c0245: the Properties panel; empty, it says that nothing is selected
  const el = $("info"); if (!html) { el.innerHTML = ""; $("propsEmpty").hidden = false; return; } el.innerHTML = html; $("propsEmpty").hidden = true;
  annotateValues(el, prov || defaultProvenance()); }
function defaultProvenance() {   // what a value of Properties comes from when its builder says nothing more
  if (!S || !S.meta) return { source: "the page", evidence: "UNKNOWN" };
  return { source: `${S.meta.name || "the document"}, read by the ${S.meta.backend || "?"} backend`, evidence: S.meta.evidence || "UNKNOWN" };
}
function annotateValues(root, prov) {   // every text with a digit, outside an element that already names its source, gets one (M1)
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT), hits = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) if (/\d/.test(n.nodeValue) && !(n.parentElement && n.parentElement.closest("[data-value], a, code, kbd"))) hits.push(n);
  for (const n of hits) { const s = document.createElement("span"); s.dataset.value = ""; s.dataset.source = prov.source; s.dataset.evidence = prov.evidence;
    s.title = `${prov.source} · evidence ${prov.evidence}`; n.replaceWith(s); s.appendChild(n); }
}
function esc(s) { return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" })[c]); }
function linkify(v) { const t = String(v); return /^https?:\/\/\S+$/i.test(t) ? `<a href="${esc(t)}" target="_blank" rel="noopener noreferrer">${esc(t)}</a>` : esc(t); }

// ---- query (c0187): the board filter. key:value terms joined by spaces (and), "|" (or), a leading "-" (not),
// * and ? wildcards, quoted values. Keys: net, ref, footprint, value, layer, side; any other key is the name of a
// part parameter; a bare value matches a reference or a net. Pure functions of a scene, run in Node by the tests.
function wildRe(v) { return new RegExp("^" + String(v).replace(/[.+^${}()[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$", "i"); }
function queryParse(text) {
  const s = String(text), groups = [[]]; let i = 0;
  while (i < s.length) {
    if (/\s/.test(s[i])) { i++; continue; }
    if (s[i] === "|") { groups.push([]); i++; continue; }
    let neg = false, key = "", val; if (s[i] === "-") { neg = true; i++; }
    let j = i; while (j < s.length && /[\w.]/.test(s[j])) j++;
    if (j > i && s[j] === ":") { key = s.slice(i, j).toLowerCase(); i = j + 1; }
    if (s[i] === "\"") { const e = s.indexOf("\"", i + 1); val = s.slice(i + 1, e < 0 ? s.length : e); i = e < 0 ? s.length : e + 1; }
    else { j = i; while (j < s.length && !/[\s|]/.test(s[j])) j++; val = s.slice(i, j); i = j; }
    groups[groups.length - 1].push({ key, neg, val, re: wildRe(val) });
  }
  return groups.filter(g => g.length);
}
function termTest(t, c) {
  const any = vs => vs.some(v => v != null && v !== "" && t.re.test(String(v)));
  let hit;
  if (t.key === "") hit = any([c.ref, ...c.nets]);
  else if (t.key === "net") hit = any(c.nets);
  else if (t.key === "layer") hit = any(c.layers);
  else if (t.key === "ref" || t.key === "footprint" || t.key === "value" || t.key === "side") hit = any([c[t.key]]);
  else { const p = c.params || {}, k = Object.keys(p).find(n => n.toLowerCase() === t.key); hit = k !== undefined && any([p[k]]); }
  return hit !== t.neg;
}
function queryTest(q, c) { return q.some(g => g.every(t => termTest(t, c))); }
function queryRun(sc, q) {   // the primitives and the parts of the board scene `sc` that the parsed query `q` matches
  const lt = new Map(sc.layers.map(l => [l.id, { tags: [l.id, l.name], side: l.side }]));
  const cn = sc.comps.map(() => new Set()), cl = sc.comps.map(() => new Set()), prims = new Set();
  for (const pr of sc.prims) {
    const L = lt.get(pr[0]) || { tags: [pr[0]], side: "" }, c = pr[4] >= 0 ? sc.comps[pr[4]] : null, net = pr[3] >= 0 ? sc.nets[pr[3]] : "";
    if (c) { if (net) cn[pr[4]].add(net); for (const t of L.tags) cl[pr[4]].add(t); }
    const ctx = { nets: net ? [net] : [], layers: L.tags, ref: c ? c.ref : "", footprint: c ? c.footprint : "", value: c ? c.value : "",
      side: c ? c.side : L.side || "", params: c ? c.params : null };
    if (queryTest(q, ctx)) prims.add(pr);
  }
  const comps = [];
  sc.comps.forEach((c, i) => { if (queryTest(q, { nets: [...cn[i]], layers: [...cl[i]], ref: c.ref, footprint: c.footprint, value: c.value, side: c.side, params: c.params })) comps.push(i); });
  return { prims, comps };
}
function similarQuery(sc, pr, ci) {   // Find similar: a query for the parts of the same footprint and value, or the same net on the same layer
  const qv = v => `"${String(v).replace(/"/g, "")}"`;
  if (ci >= 0) { const c = sc.comps[ci]; return `footprint:${qv(c.footprint)}` + (c.value ? ` value:${qv(c.value)}` : ""); }
  if (!pr) return "";
  const l = sc.layers.find(x => x.id === pr[0]), layer = `layer:${qv(l ? l.name : pr[0])}`;
  return pr[3] >= 0 ? `net:${qv(sc.nets[pr[3]])} ${layer}` : layer;
}
// ---- end query

// ---- edge (c0189): the shortest distance between the edges of two board primitives, as Altium's clearance
// measure gives it. A primitive is segments and points grown by a radius (a track: its centre line and half its
// width; a via or a round pad: its centre and radius; an arc: its centre line sampled every 2°) or filled rings
// (pads, fills, regions). The distance is exact for segments and points; overlapping shapes read 0.
function arcSample(d) {   // three points (start, mid, end) to a polyline through them
  const [x1, y1, x2, y2, x3, y3] = d, D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2));
  if (Math.abs(D) < 1e-12) return [x1, y1, x3, y3];
  const s1 = x1 * x1 + y1 * y1, s2 = x2 * x2 + y2 * y2, s3 = x3 * x3 + y3 * y3;
  const cx = (s1 * (y2 - y3) + s2 * (y3 - y1) + s3 * (y1 - y2)) / D, cy = (s1 * (x3 - x2) + s2 * (x1 - x3) + s3 * (x2 - x1)) / D, r = Math.hypot(x1 - cx, y1 - cy);
  const T = 2 * Math.PI, a1 = Math.atan2(y1 - cy, x1 - cx), a2 = Math.atan2(y2 - cy, x2 - cx), a3 = Math.atan2(y3 - cy, x3 - cx);
  const ccwSpan = ((a3 - a1) % T + T) % T, midIn = ((a2 - a1) % T + T) % T <= ccwSpan, span = midIn ? ccwSpan : ccwSpan - T;
  const n = Math.max(2, Math.ceil(Math.abs(span) / (Math.PI / 90))), out = [];
  for (let i = 0; i <= n; i++) { const t = a1 + span * i / n; out.push(cx + r * Math.cos(t), cy + r * Math.sin(t)); }
  return out;
}
function edgeShape(pr) {   // { lines: polylines, rings: filled rings, r: growth }
  const d = pr[2];
  switch (pr[1]) {
    case "s": return { lines: [[d[0], d[1], d[2], d[3]]], rings: [], r: d[4] / 2 };
    case "c": return { lines: [[d[0], d[1]]], rings: [], r: d[2] };
    case "a": return { lines: [arcSample(d)], rings: [], r: d[6] / 2 };
    case "l": return { lines: [d.slice(1)], rings: [], r: d[0] / 2 };
    case "p": case "h": return { lines: d, rings: d, r: 0, closed: true };
    case "o": return { lines: d, rings: [], r: 0, closed: true };
  }
  return null;
}
function ptSeg(px, py, x1, y1, x2, y2) {   // the closest point of a segment to a point, and the distance
  const dx = x2 - x1, dy = y2 - y1, L = dx * dx + dy * dy; let t = L ? ((px - x1) * dx + (py - y1) * dy) / L : 0; t = Math.max(0, Math.min(1, t));
  const qx = x1 + t * dx, qy = y1 + t * dy; return [Math.hypot(px - qx, py - qy), qx, qy];
}
function segSeg(a, b) {   // [distance, point on a, point on b] of two segments [x1, y1, x2, y2]
  const [ax, ay, bx, by] = a, [cx, cy, dx, dy] = b, cross = (px, py, qx, qy, rx, ry) => (qx - px) * (ry - py) - (qy - py) * (rx - px);
  const d1 = cross(cx, cy, dx, dy, ax, ay), d2 = cross(cx, cy, dx, dy, bx, by), d3 = cross(ax, ay, bx, by, cx, cy), d4 = cross(ax, ay, bx, by, dx, dy);
  if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) { const t = d1 / (d1 - d2), x = ax + t * (bx - ax), y = ay + t * (by - ay); return [0, [x, y], [x, y]]; }
  let best = null;
  for (const [p, q, flip] of [[[ax, ay], b, false], [[bx, by], b, false], [[cx, cy], a, true], [[dx, dy], a, true]]) {
    const [dd, qx, qy] = ptSeg(p[0], p[1], q[0], q[1], q[2], q[3]);
    if (!best || dd < best[0]) best = flip ? [dd, [qx, qy], p] : [dd, p, [qx, qy]]; }
  return best;
}
function edgeSegs(sh) {   // the segments of a shape (a lone point is a segment of length 0)
  const out = [];
  for (const l of sh.lines) { const n = l.length / 2;
    if (n === 1) out.push([l[0], l[1], l[0], l[1]]);
    for (let i = 0; i + 1 < n; i++) out.push([l[2 * i], l[2 * i + 1], l[2 * i + 2], l[2 * i + 3]]);
    if (sh.closed && n > 2) out.push([l[2 * n - 2], l[2 * n - 1], l[0], l[1]]); }
  return out;
}
function ringHas(rings, x, y) { let n = 0; for (const r of rings) { let c = false;
  for (let i = 0, j = r.length - 2; i < r.length; j = i, i += 2) if ((r[i + 1] > y) !== (r[j + 1] > y) && x < (r[j] - r[i]) * (y - r[i + 1]) / (r[j + 1] - r[i + 1]) + r[i]) c = !c; if (c) n++; } return n % 2 === 1; }
function edgeDistance(pa, pb) {   // { d, a, b }: the gap between the edges of two primitives and its two end points
  const A = edgeShape(pa), B = edgeShape(pb); if (!A || !B) return null;
  let best = null;
  for (const s of edgeSegs(A)) for (const t of edgeSegs(B)) { const r = segSeg(s, t); if (!best || r[0] < best[0]) best = r; }
  if (!best) return null;
  const [d, p, q] = best, gap = d - A.r - B.r;
  if (gap <= 0) return { d: 0, a: p, b: q };
  for (const [S, T] of [[A, B], [B, A]]) if (S.rings.length) { const l = T.lines[0]; if (l && ringHas(S.rings, l[0], l[1])) return { d: 0, a: [l[0], l[1]], b: [l[0], l[1]] }; }
  const ux = (q[0] - p[0]) / d, uy = (q[1] - p[1]) / d;   // the centre-line points moved out to each edge
  return { d: gap, a: [p[0] + ux * A.r, p[1] + uy * A.r], b: [q[0] - ux * B.r, q[1] - uy * B.r] };
}
function edgeBetween(ga, gb) {   // the shortest of edgeDistance over two groups of primitives (all of a pad's copper on a layer)
  let best = null; for (const a of ga) for (const b of gb) { const r = edgeDistance(a, b); if (r && (!best || r.d < best.d)) best = r; } return best;
}
// ---- end edge
