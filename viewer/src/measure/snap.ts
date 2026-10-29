// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { byLayer } from "../board/cache";
import { order } from "../board/draw";
import { ringSamples } from "../board/geometry";
import { S, view } from "../core/state";
export function snapPoints() {   // pad centres, line ends and vertices, circle centres, text anchors: where a measurement snaps
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
export function snap(x, y, free) {
  if (free) return { p: [x, y], snapped: false };   // Alt held: no snap (change c0193)
  const pts = snapPoints(), tol = 8 / view.s; let best = null, bd = tol;
  for (let i = 0; i < pts.length; i += 2) { const d = Math.hypot(pts[i] - x, pts[i + 1] - y); if (d < bd) { bd = d; best = [pts[i], pts[i + 1]]; } }
  if (best) return { p: best, snapped: true };
  const e = S.kind ? null : snapEdge(x, y, 10);
  return e ? { p: [e.x, e.y], snapped: true, edge: e.label } : { p: [x, y], snapped: false };
}
// ================================================================== edge snap (change c0193)
// Without a point within reach, a board measurement snaps to the nearest point of an edge of a visible layer: pad
// and fill borders, track borders and axis, circles, outlines and the board edge.
export const SNAP_CELL = 2;
export function buildEdges() {
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
export function snapEdge(x, y, tolPx) {
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
