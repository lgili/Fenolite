// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { P2D, S } from "../core/state";
// an arc through three points: centre, radius, start and end angles, and the direction (canvas angles, Y down)
export function arcOf(d) {
  const [x1, y1, x2, y2, x3, y3] = d, D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2));
  if (Math.abs(D) < 1e-12) return null;
  const q1 = x1 * x1 + y1 * y1, q2 = x2 * x2 + y2 * y2, q3 = x3 * x3 + y3 * y3;
  const cx = (q1 * (y2 - y3) + q2 * (y3 - y1) + q3 * (y1 - y2)) / D, cy = (q1 * (x3 - x2) + q2 * (x1 - x3) + q3 * (x2 - x1)) / D;
  const a1 = Math.atan2(y1 - cy, x1 - cx), am = Math.atan2(y2 - cy, x2 - cx), a3 = Math.atan2(y3 - cy, x3 - cx), T = 2 * Math.PI;
  const d13 = ((a3 - a1) % T + T) % T, d1m = ((am - a1) % T + T) % T;
  return { cx, cy, r: Math.hypot(x1 - cx, y1 - cy), a1, a3, ccw: d1m > d13 };
}
export function ringSamples(ring) {   // a board ring with its arcs, as points
  const p = ring.points, out = [];
  for (let i = 0; i < p.length; i += 2) { const j = (i + 2) % p.length, m = ring.mids[i / 2]; out.push([p[i], p[i + 1]]);
    if (m) { const a = arcOf([p[i], p[i + 1], m[0], m[1], p[j], p[j + 1]]); if (a) { let span = ((a.a3 - a.a1) % (2 * Math.PI) + 2 * Math.PI) % (2 * Math.PI); if (a.ccw) span -= 2 * Math.PI;
      for (let k = 1; k < 16; k++) { const t = a.a1 + span * k / 16; out.push([a.cx + a.r * Math.cos(t), a.cy + a.r * Math.sin(t)]); } } } }
  return out;
}
export function boardPath() { const bp = new P2D(); for (const r of S.board) { const pts = ringSamples(r); pts.forEach((q, k) => k ? bp.lineTo(q[0], q[1]) : bp.moveTo(q[0], q[1])); bp.closePath(); } return bp; }
