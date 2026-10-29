// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// findings: an item of a group drawn as a line, a path (a dashed creepage path too) or a marker; the group's box hides it
import { ctx, S, st, view } from "../core/state";
import { worldTf } from "../core/viewport";
export const ovGroup = o => o.group || (o.kind === "creepage" ? "analyze_creepage" : "analyze_clearance");
export function drawOverlays() {
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
