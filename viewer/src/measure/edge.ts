// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ---- edge (c0189): the shortest distance between the edges of two board primitives, as Altium's clearance
// measure gives it. A primitive is segments and points grown by a radius (a track: its centre line and half its
// width; a via or a round pad: its centre and radius; an arc: its centre line sampled every 2°) or filled rings
// (pads, fills, regions). The distance is exact for segments and points; overlapping shapes read 0.
export function arcSample(d) {   // three points (start, mid, end) to a polyline through them
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
export function edgeShape(pr) {   // { lines: polylines, rings: filled rings, r: growth }
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
export function ptSeg(px, py, x1, y1, x2, y2) {   // the closest point of a segment to a point, and the distance
  const dx = x2 - x1, dy = y2 - y1, L = dx * dx + dy * dy; let t = L ? ((px - x1) * dx + (py - y1) * dy) / L : 0; t = Math.max(0, Math.min(1, t));
  const qx = x1 + t * dx, qy = y1 + t * dy; return [Math.hypot(px - qx, py - qy), qx, qy];
}
export function segSeg(a, b) {   // [distance, point on a, point on b] of two segments [x1, y1, x2, y2]
  const [ax, ay, bx, by] = a, [cx, cy, dx, dy] = b, cross = (px, py, qx, qy, rx, ry) => (qx - px) * (ry - py) - (qy - py) * (rx - px);
  const d1 = cross(cx, cy, dx, dy, ax, ay), d2 = cross(cx, cy, dx, dy, bx, by), d3 = cross(ax, ay, bx, by, cx, cy), d4 = cross(ax, ay, bx, by, dx, dy);
  if (((d1 > 0 && d2 < 0) || (d1 < 0 && d2 > 0)) && ((d3 > 0 && d4 < 0) || (d3 < 0 && d4 > 0))) { const t = d1 / (d1 - d2), x = ax + t * (bx - ax), y = ay + t * (by - ay); return [0, [x, y], [x, y]]; }
  let best = null;
  for (const [p, q, flip] of [[[ax, ay], b, false], [[bx, by], b, false], [[cx, cy], a, true], [[dx, dy], a, true]]) {
    const [dd, qx, qy] = ptSeg(p[0], p[1], q[0], q[1], q[2], q[3]);
    if (!best || dd < best[0]) best = flip ? [dd, [qx, qy], p] : [dd, p, [qx, qy]]; }
  return best;
}
export function edgeSegs(sh) {   // the segments of a shape (a lone point is a segment of length 0)
  const out = [];
  for (const l of sh.lines) { const n = l.length / 2;
    if (n === 1) out.push([l[0], l[1], l[0], l[1]]);
    for (let i = 0; i + 1 < n; i++) out.push([l[2 * i], l[2 * i + 1], l[2 * i + 2], l[2 * i + 3]]);
    if (sh.closed && n > 2) out.push([l[2 * n - 2], l[2 * n - 1], l[0], l[1]]); }
  return out;
}
export function ringHas(rings, x, y) { let n = 0; for (const r of rings) { let c = false;
  for (let i = 0, j = r.length - 2; i < r.length; j = i, i += 2) if ((r[i + 1] > y) !== (r[j + 1] > y) && x < (r[j] - r[i]) * (y - r[i + 1]) / (r[j + 1] - r[i + 1]) + r[i]) c = !c; if (c) n++; } return n % 2 === 1; }
export function edgeDistance(pa, pb) {   // { d, a, b }: the gap between the edges of two primitives and its two end points
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
export function edgeBetween(ga, gb) {   // the shortest of edgeDistance over two groups of primitives (all of a pad's copper on a layer)
  let best = null; for (const a of ga) for (const b of gb) { const r = edgeDistance(a, b); if (r && (!best || r.d < best.d)) best = r; } return best;
}
// ---- end edge
