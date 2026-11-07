// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { textPolylines } from "../core/font";
import { P2D, S } from "../core/state";
export let qCache = new Map(), cache = null, netCache = new Map(), compCache = new Map(), textCache = new Map(), byLayer = new Map();
export function lighten(hex, f) { const n = parseInt(hex.slice(1), 16); let r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  r = Math.round(r + (255 - r) * f); g = Math.round(g + (255 - g) * f); b = Math.round(b + (255 - b) * f); return `rgb(${r},${g},${b})`; }
export function ringPath(p, flat) { p.moveTo(flat[0], flat[1]); for (let i = 2; i < flat.length; i += 2) p.lineTo(flat[i], flat[i + 1]); p.closePath(); }
export function strokePath(c, w) { let p = c.strokes.get(w); if (!p) { p = new P2D(); c.strokes.set(w, p); } return p; }
export function addPrim(c, pr) {
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
export function newCache() { return { fill: new P2D(), strokes: new Map(), outline: new P2D(), hatch: new P2D(), hb: [1e9, 1e9, -1e9, -1e9], n: 0 }; }
export function bboxOf(pr) { const d = pr[2]; switch (pr[1]) {
  case "s": return [Math.min(d[0], d[2]) - d[4] / 2, Math.min(d[1], d[3]) - d[4] / 2, Math.max(d[0], d[2]) + d[4] / 2, Math.max(d[1], d[3]) + d[4] / 2];
  case "a": { const a = pr[6], w = d[6] / 2; if (!a) return [Math.min(d[0], d[4]) - w, Math.min(d[1], d[5]) - w, Math.max(d[0], d[4]) + w, Math.max(d[1], d[5]) + w];
    return [a.cx - a.r - w, a.cy - a.r - w, a.cx + a.r + w, a.cy + a.r + w]; }
  case "c": return [d[0] - d[2], d[1] - d[2], d[0] + d[2], d[1] + d[2]];
  case "l": { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (let i = 1; i < d.length; i += 2) { x0 = Math.min(x0, d[i]); x1 = Math.max(x1, d[i]); y0 = Math.min(y0, d[i + 1]); y1 = Math.max(y1, d[i + 1]); }
    return [x0 - d[0] / 2, y0 - d[0] / 2, x1 + d[0] / 2, y1 + d[0] / 2]; }
  default: { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const ring of d) for (let i = 0; i < ring.length; i += 2) {
    x0 = Math.min(x0, ring[i]); x1 = Math.max(x1, ring[i]); y0 = Math.min(y0, ring[i + 1]); y1 = Math.max(y1, ring[i + 1]); } return [x0, y0, x1, y1]; } } }
export function buildCaches() {
  qCache = new Map(); cache = new Map(); netCache = new Map(); compCache = new Map(); textCache = new Map(); byLayer = new Map();
  for (const l of S.layers) { cache.set(l.id, newCache()); byLayer.set(l.id, []); textCache.set(l.id, { strokes: new Map(), n: 0 }); }
  for (const pr of S.prims) { const c = cache.get(pr[0]); if (c) { addPrim(c, pr); byLayer.get(pr[0]).push([pr, bboxOf(pr)]); } }
  for (const t of S.texts) { const tc = textCache.get(t[0]); if (!tc) continue; tc.n++;
    const p = strokePath(tc, Math.max(t[5], 0.05)); for (const pl of textPolylines(t)) { p.moveTo(pl[0][0], pl[0][1]); for (let k = 1; k < pl.length; k++) p.lineTo(pl[k][0], pl[k][1]);
      if (pl.length === 1) p.lineTo(pl[0][0] + 1e-4, pl[0][1]); } }
}
export function selCache(map, key, test) {
  if (map.has(key)) return map.get(key);
  const m = new Map(); for (const l of S.layers) m.set(l.id, newCache());
  for (const pr of S.prims) if (test(pr)) { const c = m.get(pr[0]); if (c) addPrim(c, pr); }
  map.set(key, m); return m;
}
