// ================================================================== units: millimetres or mil (Q), as in Altium
const MIL_MM = 0.0254;
let UNIT = (() => { try { return localStorage.getItem("fenolite.view.unit") === "mil" ? "mil" : "mm"; } catch (e) { return "mm"; } })();
function fmtLen(mm) { return UNIT === "mil" ? `${(mm / MIL_MM).toFixed(2)} mil` : `${mm.toFixed(3)} mm`; }
function fmtNm(nm) { return fmtLen(nm / 1e6); }
function fmtPair(a, b) { return UNIT === "mil" ? `${(a / MIL_MM).toFixed(2)} × ${(b / MIL_MM).toFixed(2)} mil` : `${a.toFixed(3)} × ${b.toFixed(3)} mm`; }

// <decodeV1> c0182: a compact board scene (fenolite.view_scene.v1, view/compact.py) back to its v0 primitives
function decodeV1(sc) {
  const p = sc.p1; if (!p) return sc;
  const D = p.D, FIXED = { c: 1, s: 2, a: 3 }, last = new Map(), prims = new Array(p.K.length);
  let at = 0, cx = 0, cy = 0;
  const pts = (n, x, y) => { const out = new Array(2 * n); for (let i = 0; i < n; i++) { x += D[at++]; y += D[at++]; out[2 * i] = x; out[2 * i + 1] = y; } return out; };
  for (let k = 0; k < p.K.length; k++) {
    const kind = p.K[k]; let v;
    if (kind === "p" || kind === "o" || kind === "h") { const count = D[at++]; v = []; let rx = cx, ry = cy;
      for (let r = 0; r < count; r++) { const ring = pts(D[at++], rx, ry); if (ring.length) { rx = ring[0]; ry = ring[1]; if (r === 0) { cx = rx; cy = ry; } } v.push(ring); } }
    else if (kind === "l") { const n = D[at++], w = D[at++]; const f = pts(n, cx, cy); cx = f[0]; cy = f[1]; v = [w, ...f]; }
    else { const f = pts(FIXED[kind], cx, cy); cx = f[0]; cy = f[1]; f.push(D[at++]); v = f; }
    const s = p.S[k], n = (last.get(s) || 0) + p.SN[k]; last.set(s, n); const t = p.strings[s];
    prims[k] = [p.layers[p.L[k]], kind, v, p.N[k], p.C[k], t.includes("\u0001") ? t.replace("\u0001", String(n)) : t];
  }
  delete sc.p1; sc.prims = prims; sc.schema = "fenolite.view_scene.v0"; return sc;
}
// </decodeV1>
async function unpackScene(v) {   // c0182: a scene of a standalone page, "gz:" + base64 of its gzipped JSON
  if (typeof v !== "string") return v;
  const bin = Uint8Array.from(atob(v.slice(3)), c => c.charCodeAt(0));
  const text = await new Response(new Blob([bin]).stream().pipeThrough(new DecompressionStream("gzip"))).text();
  return JSON.parse(text);
}
function primToMM(pr, f) { const d = pr[2];
  if (pr[1] === "p" || pr[1] === "o" || pr[1] === "h") pr[2] = d.map(r => r.map(f)); else pr[2] = d.map(f);
  if (pr[1] === "a") pr.push(arcOf(pr[2])); }
function diffToMM(sc) {   // c0184: the changes of --compare, in micrometres like the scene
  const D = sc.diff; if (!D) return; const f = v => v * MM;
  for (const pr of [...(D.added || []), ...(D.removed || [])]) primToMM(pr, f);
  for (const m of D.moved || []) { m.from = m.from.map(f); m.to = m.to.map(f); }
  for (const c of D.changes) if (c.box) c.box = c.box.map(f);
}
function toMM(scene) {
  decodeV1(scene);
  if (scene.mm) return scene; scene.mm = true; diffToMM(scene); checkToMM(scene);
  for (const p of scene.pads || []) { p.x *= MM; p.y *= MM; }
  const f = v => v * MM;
  for (const pr of scene.prims) primToMM(pr, f);
  for (const t of scene.texts) for (const k of [1, 2, 3, 4, 5]) t[k] = t[k] * MM;
  for (const c of scene.comps) { c.x *= MM; c.y *= MM; if (c.bbox) c.bbox = c.bbox.map(f); }
  for (const r of scene.board) { r.points = r.points.map(f); r.mids = r.mids.map(m => m ? m.map(f) : null); }
  scene.bounds = scene.bounds.map(f); scene.board3d.thickness *= MM;
  for (const b of scene.bodies) { b.ring = b.ring.map(f); b.z0 *= MM; b.z1 *= MM; if (b.zs) b.zs = b.zs.map(f); }
  for (const o of scene.overlays || []) { o.pts = o.pts.map(p => p.map(f)); if (o.bbox) o.bbox = o.bbox.map(f); }
  return scene;
}
// an arc through three points: centre, radius, start and end angles, and the direction (canvas angles, Y down)
function arcOf(d) {
  const [x1, y1, x2, y2, x3, y3] = d, D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2));
  if (Math.abs(D) < 1e-12) return null;
  const q1 = x1 * x1 + y1 * y1, q2 = x2 * x2 + y2 * y2, q3 = x3 * x3 + y3 * y3;
  const cx = (q1 * (y2 - y3) + q2 * (y3 - y1) + q3 * (y1 - y2)) / D, cy = (q1 * (x3 - x2) + q2 * (x1 - x3) + q3 * (x2 - x1)) / D;
  const a1 = Math.atan2(y1 - cy, x1 - cx), am = Math.atan2(y2 - cy, x2 - cx), a3 = Math.atan2(y3 - cy, x3 - cx), T = 2 * Math.PI;
  const d13 = ((a3 - a1) % T + T) % T, d1m = ((am - a1) % T + T) % T;
  return { cx, cy, r: Math.hypot(x1 - cx, y1 - cy), a1, a3, ccw: d1m > d13 };
}
function ringSamples(ring) {   // a board ring with its arcs, as points
  const p = ring.points, out = [];
  for (let i = 0; i < p.length; i += 2) { const j = (i + 2) % p.length, m = ring.mids[i / 2]; out.push([p[i], p[i + 1]]);
    if (m) { const a = arcOf([p[i], p[i + 1], m[0], m[1], p[j], p[j + 1]]); if (a) { let span = ((a.a3 - a.a1) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI); if (a.ccw) span -= 2 * Math.PI;
      for (let k = 1; k < 16; k++) { const t = a.a1 + span * k / 16; out.push([a.cx + a.r * Math.cos(t), a.cy + a.r * Math.sin(t)]); } } } }
  return out;
}
function boardPath() { const bp = new P2D(); for (const r of S.board) { const pts = ringSamples(r); pts.forEach((q, k) => k ? bp.lineTo(q[0], q[1]) : bp.moveTo(q[0], q[1])); bp.closePath(); } return bp; }

function lighten(hex, f) { const n = parseInt(hex.slice(1), 16); let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  r = Math.round(r + (255 - r) * f); g = Math.round(g + (255 - g) * f); b = Math.round(b + (255 - b) * f); return `rgb(${r},${g},${b})`; }
function ringPath(p, flat) { p.moveTo(flat[0], flat[1]); for (let i = 2; i < flat.length; i += 2) p.lineTo(flat[i], flat[i + 1]); p.closePath(); }
function strokePath(c, w) { let p = c.strokes.get(w); if (!p) { p = new P2D(); c.strokes.set(w, p); } return p; }
function addPrim(c, pr) {
  const k = pr[1], d = pr[2];
  if (k === "s") { const p = strokePath(c, d[4]); p.moveTo(d[0], d[1]); p.lineTo(d[2], d[3]); if (d[0] === d[2] && d[1] === d[3]) p.lineTo(d[2] + 1e-4, d[3]); }
  else if (k === "a") { const a = pr[6], p = strokePath(c, d[6]); if (!a) { p.moveTo(d[0], d[1]); p.lineTo(d[4], d[5]); } else { p.moveTo(d[0], d[1]); p.arc(a.cx, a.cy, a.r, a.a1, a.a3, a.ccw); } }
  else if (k === "l") { const p = strokePath(c, d[0]); p.moveTo(d[1], d[2]); for (let i = 3; i < d.length; i += 2) p.lineTo(d[i], d[i + 1]); if (d.length === 3) p.lineTo(d[1] + 1e-4, d[2]); }
  else if (k === "c") { c.fill.moveTo(d[0] + d[2], d[1]); c.fill.arc(d[0], d[1], d[2], 0, 2 * Math.PI); c.fill.closePath(); }
  else if (k === "p") { for (const r of d) ringPath(c.fill, r); }
  else if (k === "o") { for (const r of d) ringPath(c.outline, r); }
  else if (k === "h") { for (const r of d) { ringPath(c.hatch, r); for (let i = 0; i < r.length; i += 2) {   // c0183: a keep-out or a finding, hatched
    c.hb[0] = Math.min(c.hb[0], r[i]); c.hb[1] = Math.min(c.hb[1], r[i + 1]); c.hb[2] = Math.max(c.hb[2], r[i]); c.hb[3] = Math.max(c.hb[3], r[i + 1]); } } }
  c.n++;
}
function newCache() { return { fill: new P2D(), strokes: new Map(), outline: new P2D(), hatch: new P2D(), hb: [1e9, 1e9, -1e9, -1e9], n: 0 }; }
function bboxOf(pr) { const d = pr[2]; switch (pr[1]) {
  case "s": return [Math.min(d[0], d[2]) - d[4] / 2, Math.min(d[1], d[3]) - d[4] / 2, Math.max(d[0], d[2]) + d[4] / 2, Math.max(d[1], d[3]) + d[4] / 2];
  case "a": { const a = pr[6], w = d[6] / 2; if (!a) return [Math.min(d[0], d[4]) - w, Math.min(d[1], d[5]) - w, Math.max(d[0], d[4]) + w, Math.max(d[1], d[5]) + w];
    return [a.cx - a.r - w, a.cy - a.r - w, a.cx + a.r + w, a.cy + a.r + w]; }
  case "c": return [d[0] - d[2], d[1] - d[2], d[0] + d[2], d[1] + d[2]];
  case "l": { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (let i = 1; i < d.length; i += 2) { x0 = Math.min(x0, d[i]); x1 = Math.max(x1, d[i]); y0 = Math.min(y0, d[i + 1]); y1 = Math.max(y1, d[i + 1]); }
    return [x0 - d[0] / 2, y0 - d[0] / 2, x1 + d[0] / 2, y1 + d[0] / 2]; }
  default: { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const ring of d) for (let i = 0; i < ring.length; i += 2) {
    x0 = Math.min(x0, ring[i]); x1 = Math.max(x1, ring[i]); y0 = Math.min(y0, ring[i + 1]); y1 = Math.max(y1, ring[i + 1]); } return [x0, y0, x1, y1]; } } }
function buildCaches() {
  qCache = new Map(); cache = new Map(); netCache = new Map(); compCache = new Map(); textCache = new Map(); byLayer = new Map();
  for (const l of S.layers) { cache.set(l.id, newCache()); byLayer.set(l.id, []); textCache.set(l.id, { strokes: new Map(), n: 0 }); }
  for (const pr of S.prims) { const c = cache.get(pr[0]); if (c) { addPrim(c, pr); byLayer.get(pr[0]).push([pr, bboxOf(pr)]); } }
  for (const t of S.texts) { const tc = textCache.get(t[0]); if (!tc) continue; tc.n++;
    const p = strokePath(tc, Math.max(t[5], 0.05)); for (const pl of textPolylines(t)) { p.moveTo(pl[0][0], pl[0][1]); for (let k = 1; k < pl.length; k++) p.lineTo(pl[k][0], pl[k][1]);
      if (pl.length === 1) p.lineTo(pl[0][0] + 1e-4, pl[0][1]); } }
}
function selCache(map, key, test) {
  if (map.has(key)) return map.get(key);
  const m = new Map(); for (const l of S.layers) m.set(l.id, newCache());
  for (const pr of S.prims) if (test(pr)) { const c = m.get(pr[0]); if (c) addPrim(c, pr); }
  map.set(key, m); return m;
}

