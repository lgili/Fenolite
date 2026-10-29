function measure() { const r = cv.getBoundingClientRect(); dpr = window.devicePixelRatio || 1; W = r.width || W; H = r.height || H;
cv.width = Math.max(1, Math.round(W * dpr)); cv.height = Math.max(1, Math.round(H * dpr)); }
let fitted = false;
function resize() { measure(); if (st.mode3d) resize3D(); if (S && !fitted) fit(); else draw(); }
new ResizeObserver(resize).observe($("wrap"));
function m() { return view.mirror ? -1 : 1; }
function w2s(x, y) { return [W / 2 + m() * (x - view.cx) * view.s, H / 2 + (y - view.cy) * view.s]; }
function s2w(X, Y) { return [view.cx + m() * (X - W / 2) / view.s, view.cy + (Y - H / 2) / view.s]; }
function worldTf(g) { (g || ctx).setTransform(dpr * m() * view.s, 0, 0, dpr * view.s, dpr * (W / 2 - m() * view.cx * view.s), dpr * (H / 2 - view.cy * view.s)); }
function fit(b, quick) { if (!S || S.kind === "table") return; measure();
b = b || S.bounds; const w = b[2] - b[0], h = b[3] - b[1];
view.cx = (b[0] + b[2]) / 2; view.cy = (b[1] + b[3]) / 2;
view.s = Math.max(0.2, Math.min(Math.max(W - 40, 60) / Math.max(w, 1), Math.max(H - 40, 60) / Math.max(h, 1)));
fitted = W > 100 && H > 100; if (quick) drawInteractive(); else draw(); }
const VIEWL = id => id.startsWith("View.");
function activeSide() { return view.mirror ? "bottom" : "top"; }
function order() {
const L = S.layers.filter(l => vis.get(l.id));
if (st.single) return L.filter(l => l.id === st.cur || l.id === "View.Drill" || l.id === "View.Outline").map(l => [l, 1]);
const act = activeSide(), other = act === "top" ? "bottom" : "top";
const both = L.filter(l => l.side === "both" && !VIEWL(l.id)), oth = L.filter(l => l.side === other), actL = L.filter(l => l.side === act), post = L.filter(l => VIEWL(l.id));
if (act === "bottom") actL.reverse();
let out = [...oth.map(l => [l, st.opac]), ...both.map(l => [l, 1]), ...actL.map(l => [l, 1]), ...post.map(l => [l, 1])];
const ci = out.findIndex(e => e[0].id === st.cur); if (ci >= 0) { const [e] = out.splice(ci, 1); e[1] = 1; out.splice(out.length - post.length, 0, e); }
return out;
}
function paintCache(g, c, lid, color, alpha, unit) {
if (!c || !c.n) return;
g.globalAlpha = alpha;
if (lid === "View.Drill") { g.fillStyle = color; g.fill(c.fill, "nonzero"); g.strokeStyle = color; g.lineCap = "round"; for (const [w, p] of c.strokes) { g.lineWidth = Math.max(w, 1 / unit); g.stroke(p); } return; }
g.fillStyle = color; g.fill(c.fill, "evenodd");
g.strokeStyle = color; g.lineCap = "round"; g.lineJoin = "round";
for (const [w, p] of c.strokes) { g.lineWidth = Math.max(w, 1 / unit); g.stroke(p); }
if (lid === "View.ZoneOutline" || lid === "View.ZoneEdge") g.setLineDash([6 / unit, 4 / unit]);
g.lineWidth = 1 / unit; g.stroke(c.outline); g.setLineDash([]);
if (c.hb[2] >= c.hb[0]) { const [x0, y0, x1, y1] = c.hb, step = 8 / unit;
g.save(); g.clip(c.hatch, "evenodd"); g.lineWidth = 1 / unit; g.beginPath();
for (let t = x0 - (y1 - y0); t <= x1; t += step) { g.moveTo(t, y0); g.lineTo(t + (y1 - y0), y1); } g.stroke(); g.restore();
g.lineWidth = 1.5 / unit; g.stroke(c.hatch); }
}
function paintTexts(g, lid, color, alpha, unit) {
const tc = textCache.get(lid); if (!tc || !tc.n) return;
g.globalAlpha = alpha; g.strokeStyle = color; g.lineCap = "round"; g.lineJoin = "round";
for (const [w, p] of tc.strokes) { g.lineWidth = Math.max(w, 0.6 / unit); g.stroke(p); }
}
function draw() {
if (S && S.kind === "table") return;
if (S && S.kind === "schematic") return drawSch();
if (!S || st.mode3d) return;
const th = boardTheme(S.theme || {});
ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = th.background || "#15171b"; ctx.fillRect(0, 0, cv.width, cv.height);
worldTf(); ctx.globalAlpha = 1; ctx.fillStyle = th.board || "#050505"; ctx.fill(boardPath(), "evenodd");
drawDotGrid();
const qy = st.query && st.query.prims.size ? st.query : null, picked = st.selNet >= 0 || st.selComp >= 0;
const ord = order(), sel = picked || !!qy, other = HL_ALPHA[st.hl] ?? HL_ALPHA.dim;
const dim = S.diff && st.diff && S.diff.kind === "board" ? 0.35 : 1;
for (const [l, a00] of ord) { const a0 = a00 * dim, a = a0 * (l.alpha ?? 1); paintCache(ctx, cache.get(l.id), l.id, layerColor(l), sel ? a * other : a, view.s);
if (view.s * 0.4 > 1) paintTexts(ctx, l.id, layerColor(l), sel ? a * other : a, view.s); }
if (qy) { const mq = selCache(qCache, qy.text, pr => qy.prims.has(pr)); for (const [l] of ord) paintCache(ctx, mq.get(l.id), l.id, lighten(layerColor(l), 0.45), 1, view.s);
ctx.globalAlpha = 1; ctx.strokeStyle = "#fff"; ctx.lineWidth = 1 / view.s;
for (const ci of qy.comps.slice(0, 2000)) { const b = S.comps[ci].bbox; if (b) ctx.strokeRect(b[0] - 0.2, b[1] - 0.2, b[2] - b[0] + 0.4, b[3] - b[1] + 0.4); } }
if (picked) {
const mm = st.selNet >= 0 ? selCache(netCache, st.selNet, pr => pr[3] === st.selNet) : selCache(compCache, st.selComp, pr => pr[4] === st.selComp);
for (const [l] of ord) paintCache(ctx, mm.get(l.id), l.id, lighten(layerColor(l), 0.45), 1, view.s);
if (st.selComp >= 0 && S.comps[st.selComp].bbox) { const b = S.comps[st.selComp].bbox; ctx.globalAlpha = 1; ctx.strokeStyle = "#fff";
ctx.lineWidth = 1.5 / view.s; ctx.setLineDash([5 / view.s, 3 / view.s]); ctx.strokeRect(b[0] - 0.3, b[1] - 0.3, b[2] - b[0] + 0.6, b[3] - b[1] + 0.6); ctx.setLineDash([]); }
}
if (VARIANT && S.variants) { worldTf(); ctx.globalAlpha = 0.6; ctx.fillStyle = th.board || "#050505";
for (const c of S.comps) if (c.bbox && notFitted(c.ref)) { const b = c.bbox; ctx.fillRect(b[0], b[1], b[2] - b[0], b[3] - b[1]); }
drawVariantMarks(S.comps.map(c => [c.ref, c.bbox])); }
drawDiff(); drawOverlays(); drawRoleOverlays(); drawCheck(); drawEdge(); drawMarks(); drawMeasure(); linkLater();
$("zoomv").textContent = `zoom ${view.s.toFixed(1)} px/mm`;
}
