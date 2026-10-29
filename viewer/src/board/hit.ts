// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { byLayer } from "./cache";
import { order } from "./draw";
import { view } from "../core/state";
import { s2w } from "../core/viewport";
// ================================================================== hit test (2D)
export function segDist(px, py, x1, y1, x2, y2) { const dx = x2 - x1, dy = y2 - y1, L = dx * dx + dy * dy; let t = L ? ((px - x1) * dx + (py - y1) * dy) / L : 0;
  t = Math.max(0, Math.min(1, t)); return Math.hypot(px - x1 - t * dx, py - y1 - t * dy); }
export function inRing(px, py, r) { let c = false; for (let i = 0, j = r.length - 2; i < r.length; j = i, i += 2) {
  const xi = r[i], yi = r[i + 1], xj = r[j], yj = r[j + 1]; if (((yi > py) !== (yj > py)) && (px < (xj - xi) * (py - yi) / (yj - yi) + xi)) c = !c; } return c; }
export function hitPrim(pr, x, y, tol) { const d = pr[2]; switch (pr[1]) {
  case "s": return segDist(x, y, d[0], d[1], d[2], d[3]) <= d[4] / 2 + tol;
  case "c": return Math.hypot(x - d[0], y - d[1]) <= d[2] + tol;
  case "l": for (let i = 1; i + 3 < d.length; i += 2) if (segDist(x, y, d[i], d[i + 1], d[i + 2], d[i + 3]) <= d[0] / 2 + tol) return true; return d.length === 3 && Math.hypot(x - d[1], y - d[2]) <= d[0] / 2 + tol;
  case "a": { const a = pr[6]; if (!a) return segDist(x, y, d[0], d[1], d[4], d[5]) <= d[6] / 2 + tol; if (Math.abs(Math.hypot(x - a.cx, y - a.cy) - a.r) > d[6] / 2 + tol) return false;
    const T = 2 * Math.PI, t = Math.atan2(y - a.cy, x - a.cx); let span = ((a.a3 - a.a1) % T + T) % T, at = ((t - a.a1) % T + T) % T; if (a.ccw) { span = T - span; at = ((a.a1 - t) % T + T) % T; } return at <= span; }
  case "p": case "h": { let n = 0; for (const r of d) if (inRing(x, y, r)) n++; return n % 2 === 1; }
  case "o": for (const r of d) for (let i = 0; i < r.length; i += 2) { const j = (i + 2) % r.length; if (segDist(x, y, r[i], r[i + 1], r[j], r[j + 1]) <= tol) return true; } return false; }
  return false; }
export function pick(X, Y) {
  const [x, y] = s2w(X, Y), tol = 3 / view.s;
  const layers = order().map(e => e[0]).reverse().filter(l => l.id !== "View.Drill" && l.id !== "View.Outline");
  const outl = (l): any => l.id === "View.ZoneOutline" || l.id === "View.ZoneEdge";
  layers.sort((a, b) => outl(a) - outl(b));   // copper before zone outlines
  for (const l of layers) {
    for (const [pr, b] of byLayer.get(l.id) || []) { if (x < b[0] - tol || x > b[2] + tol || y < b[1] - tol || y > b[3] + tol) continue;
      if (hitPrim(pr, x, y, tol)) return { layer: l, pr }; } }
  return null;
}
