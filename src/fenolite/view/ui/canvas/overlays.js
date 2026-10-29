// findings: an item of a group drawn as a line, a path (a dashed creepage path too) or a marker; the group's box hides it
const ovGroup = o => o.group || (o.kind === "creepage" ? "analyze_creepage" : "analyze_clearance");
function drawOverlays() {
  if (!S.overlays || !S.overlays.length) return;
  worldTf(); ctx.globalAlpha = 1;
  S.overlays.forEach((o, i) => {
    if (st.ovOff.has(ovGroup(o))) return;
    const sel = i === st.selOv, u = 1 / view.s;
    ctx.strokeStyle = o.color; ctx.lineWidth = (sel ? 4 : 2.5) * u; ctx.setLineDash(o.kind === "creepage" ? [5 * u, 3 * u] : []);
    if (o.pts.length > 1) { ctx.beginPath(); o.pts.forEach((p, k) => k ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.stroke(); }
    ctx.setLineDash([]);
    const p = o.kind === "path" && o.pts.length === 3 ? o.pts[1] : o.pts[0], r = (sel ? 9 : 6) * u;
    ctx.beginPath(); ctx.arc(p[0], p[1], r, 0, 2 * Math.PI); ctx.stroke();
    if (o.kind === "point") { ctx.beginPath(); for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { ctx.moveTo(p[0] + dx * 0.5 * r, p[1] + dy * 0.5 * r); ctx.lineTo(p[0] + dx * 1.8 * r, p[1] + dy * 1.8 * r); } ctx.stroke(); }
    if (sel && o.bbox) { const b = o.bbox; ctx.lineWidth = 1.5 * u; ctx.setLineDash([6 * u, 4 * u]); ctx.strokeRect(b[0], b[1], b[2] - b[0], b[3] - b[1]); ctx.setLineDash([]); }
  });
}
function snapPoints() {   // pad centres, line ends and vertices, circle centres, text anchors: where a measurement snaps
  if (S.__snaps) return S.__snaps; const out = [];
  if (S.kind === "schematic") {
    for (const p of S.prims) { if (p.p && p.k !== "t") for (let i = 0; i < p.p.length; i += 2) out.push(p.p[i], p.p[i + 1]);
      else if (p.k === "e" || p.k === "a" || p.k === "t") out.push(p.x, p.y);
      else if (p.b) out.push(p.b[0], p.b[1], p.b[2], p.b[3]); } }
  else {
    for (const p of S.pads || []) out.push(p.x, p.y);
    for (const pr of S.prims) { const d = pr[2];
      if (pr[1] === "s") out.push(d[0], d[1], d[2], d[3]); else if (pr[1] === "a") out.push(d[0], d[1], d[4], d[5]);
      else if (pr[1] === "c") out.push(d[0], d[1]); else if (pr[1] === "l") for (let i = 1; i + 1 < d.length; i += 2) out.push(d[i], d[i + 1]);
      else if ((pr[1] === "p" || pr[1] === "o") && d.length === 1 && d[0].length <= 128) for (let i = 0; i < d[0].length; i += 2) out.push(d[0][i], d[0][i + 1]); } }
  S.__snaps = out; return out;
}
function snap(x, y, free) {
  if (free) return { p: [x, y], snapped: false };   // Alt held: no snap (change c0193)
  const pts = snapPoints(), tol = 8 / view.s; let best = null, bd = tol;
  for (let i = 0; i < pts.length; i += 2) { const d = Math.hypot(pts[i] - x, pts[i + 1] - y); if (d < bd) { bd = d; best = [pts[i], pts[i + 1]]; } }
  if (best) return { p: best, snapped: true };
  const e = S.kind ? null : snapEdge(x, y, 10);
  return e ? { p: [e.x, e.y], snapped: true, edge: e.label } : { p: [x, y], snapped: false };
}
