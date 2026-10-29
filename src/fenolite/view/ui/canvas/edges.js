const SNAP_CELL = 2;
function buildEdges() {
const E = [], C = [], grid = new Map();
const put = (x0, y0, x1, y1, ref) => { for (let i = Math.floor(x0 / SNAP_CELL); i <= Math.floor(x1 / SNAP_CELL); i++) for (let j = Math.floor(y0 / SNAP_CELL); j <= Math.floor(y1 / SNAP_CELL); j++) {
const k = i + "," + j; let c = grid.get(k); if (!c) { c = []; grid.set(k, c); } c.push(ref); } };
const seg = (x1, y1, x2, y2, label) => { E.push([x1, y1, x2, y2, label]); put(Math.min(x1, x2), Math.min(y1, y2), Math.max(x1, x2), Math.max(y1, y2), ["e", E.length - 1]); };
const circ = (cx, cy, r, label) => { C.push([cx, cy, r, label]); put(cx - r, cy - r, cx + r, cy + r, ["c", C.length - 1]); };
const poly = (flat, label) => { for (let i = 0; i + 3 < flat.length; i += 2) seg(flat[i], flat[i + 1], flat[i + 2], flat[i + 3], `edge · ${label}`); };
for (const [l] of order()) {
for (const [pr] of byLayer.get(l.id) || []) { const d = pr[2], name = pr[5] || l.name;
if (pr[1] === "c") circ(d[0], d[1], d[2], `edge · ${name}`);
else if (pr[1] === "s") { const w = d[4] / 2, dx = d[2] - d[0], dy = d[3] - d[1], n = Math.hypot(dx, dy) || 1, ox = -dy / n * w, oy = dx / n * w;
seg(d[0], d[1], d[2], d[3], `axis · ${name}`);
if (w > 0.05) { seg(d[0] + ox, d[1] + oy, d[2] + ox, d[3] + oy, `edge · ${name}`); seg(d[0] - ox, d[1] - oy, d[2] - ox, d[3] - oy, `edge · ${name}`);
circ(d[0], d[1], w, `edge · ${name}`); circ(d[2], d[3], w, `edge · ${name}`); } }
else if (pr[1] === "a") { const a = pr[6]; if (!a) continue; const T = 2 * Math.PI; let span = ((a.a3 - a.a1) % T + T) % T; if (a.ccw) span -= T;
const n = Math.max(6, Math.ceil(Math.abs(span) / 0.15));
for (const [r, lab] of [[a.r, "axis"], [a.r + d[6] / 2, "edge"], [a.r - d[6] / 2, "edge"]]) { if (r <= 0) continue;
for (let k = 0; k < n; k++) { const t0 = a.a1 + span * k / n, t1 = a.a1 + span * (k + 1) / n;
seg(a.cx + r * Math.cos(t0), a.cy + r * Math.sin(t0), a.cx + r * Math.cos(t1), a.cy + r * Math.sin(t1), `${lab} · ${name}`); } } }
else if (pr[1] === "l") poly(d.slice(1), name);
else if (pr[1] === "p" || pr[1] === "o") for (const r of d) poly([...r, r[0], r[1]], name); } }
for (const r of S.board) { const pts = ringSamples(r).flat(); poly([...pts, pts[0], pts[1]], "board edge"); }
return { E, C, grid };
}
function snapEdge(x, y, tolPx) {
const key = order().map(e => e[0].id).join("|"); if (!S.__edges || S.__edgeKey !== key) { S.__edgeKey = key; S.__edges = buildEdges(); }
const tol = tolPx / view.s, sn = S.__edges, seen = new Set(); let be = null, bed = tol;
for (let i = Math.floor((x - tol) / SNAP_CELL); i <= Math.floor((x + tol) / SNAP_CELL); i++) for (let j = Math.floor((y - tol) / SNAP_CELL); j <= Math.floor((y + tol) / SNAP_CELL); j++) {
for (const ref of sn.grid.get(i + "," + j) || []) { const k = ref[0] + ref[1]; if (seen.has(k)) continue; seen.add(k);
if (ref[0] === "e") { const e = sn.E[ref[1]], dx = e[2] - e[0], dy = e[3] - e[1], L = dx * dx + dy * dy;
let t = L ? ((x - e[0]) * dx + (y - e[1]) * dy) / L : 0; t = Math.max(0, Math.min(1, t)); const qx = e[0] + t * dx, qy = e[1] + t * dy, dd = Math.hypot(qx - x, qy - y);
if (dd < bed) { bed = dd; be = { x: qx, y: qy, label: e[4] }; } }
else { const c = sn.C[ref[1]], r0 = Math.hypot(x - c[0], y - c[1]) || 1e-9, dd = Math.abs(r0 - c[2]);
if (dd < bed) { bed = dd; be = { x: c[0] + (x - c[0]) * c[2] / r0, y: c[1] + (y - c[1]) * c[2] / r0, label: c[3] }; } } } }
return be;
}
function drawMeasure(g, preview) {
g = g || ctx; if (!st.measure && !st.mpts.length) return; worldTf(g); g.globalAlpha = 1; const C = "#00e08a"; g.strokeStyle = C; g.lineWidth = 1.5 / view.s;
const mark = (q, on) => { const r = 4 / view.s; g.strokeRect(q[0] - r, q[1] - r, 2 * r, 2 * r); if (on) { g.beginPath(); g.moveTo(q[0] - 2 * r, q[1]); g.lineTo(q[0] + 2 * r, q[1]); g.moveTo(q[0], q[1] - 2 * r); g.lineTo(q[0], q[1] + 2 * r); g.stroke(); } };
if (preview && st.mhover) { mark(st.mhover.p, st.mhover.snapped); if (st.mhover.edge && !st.mpts.length) $("coord").textContent = `snap: ${st.mhover.edge}`; }
if (!st.mpts.length) return;
const a = st.mpts[0], b = st.mpts[1] || (preview && st.mhover && st.mhover.p);
if (!preview || !st.mpts[1]) mark(a, true); if (!b || (preview && st.mpts[1])) return;
g.beginPath(); g.moveTo(a[0], a[1]); g.lineTo(b[0], b[1]); g.stroke(); if (st.mpts[1]) mark(b, true);
const d = Math.hypot(b[0] - a[0], b[1] - a[1]), txt = `${fmtLen(d)}   Δx ${fmtLen(Math.abs(b[0] - a[0]))}   Δy ${fmtLen(Math.abs(b[1] - a[1]))}`;
g.setTransform(dpr, 0, 0, dpr, 0, 0); const P = w2s(b[0], b[1]); g.font = "600 13px system-ui"; const w = g.measureText(txt).width;
g.fillStyle = "#000c"; g.fillRect(P[0] + 8, P[1] - 28, w + 12, 20); g.fillStyle = C; g.fillText(txt, P[0] + 14, P[1] - 13); worldTf(g);
$("coord").textContent = `measure: ${txt}`; $("coord").title = "Measured on the drawing, between points of the model; Fenolite's computation";
}
function measureClick(X, Y, free) { const [x, y] = s2w(X, Y), q = snap(x, y, free).p; if (st.mpts.length >= 2) st.mpts = []; st.mpts.push(q); draw(); }
