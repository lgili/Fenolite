// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// --- hit test
import { inRing, segDist } from "../board/hit";
import { S, view } from "../core/state";
import { s2w } from "../core/viewport";
export function schHitPrim(p, x, y, tol) {
  switch (p.k) {
    case "l": { const q = p.p; if (q.length === 2) return Math.hypot(x - q[0], y - q[1]) <= tol + p.w / 2; for (let i = 0; i + 3 < q.length; i += 2) if (segDist(x, y, q[i], q[i + 1], q[i + 2], q[i + 3]) <= p.w / 2 + tol) return true; return false; }
    case "g": return inRing(x, y, p.p) || p.p.some((_, i) => i % 2 === 0 && i + 3 < p.p.length && segDist(x, y, p.p[i], p.p[i + 1], p.p[i + 2], p.p[i + 3]) <= tol);
    case "r": case "x": case "i": { const b = p.b; return x >= b[0] - tol && x <= b[2] + tol && y >= b[1] - tol && y <= b[3] + tol; }
    case "e": case "a": return ((x - p.x) / (p.rx + tol)) ** 2 + ((y - p.y) / (p.ry + tol)) ** 2 <= 1;
    case "b": { const q = p.p; for (let i = 0; i + 3 < q.length; i += 2) if (segDist(x, y, q[i], q[i + 1], q[i + 2], q[i + 3]) <= p.w / 2 + tol) return true; return false; }
    case "t": { if (!p.sb) return false; const [w, h] = p.sb, c = [1, 0, -1, 0][p.rot || 0], s = [0, 1, 0, -1][p.rot || 0];
      const dx = x - p.x, dy = y - p.y, u = dx * c - dy * s, v = dx * s + dy * c;   // into the text's own frame
      const u0 = p.h === "left" ? 0 : p.h === "right" ? -w : -w / 2, v0 = p.v === "top" ? 0 : p.v === "center" ? -h / 2 : -h;
      return u >= u0 - tol && u <= u0 + w + tol && v >= v0 - tol && v <= v0 + h + tol; }
  }
  return false;
}
export const PRIORITY = { pin: 0, wire: 1, bus: 1, entryline: 1, junction: 1, label: 1, power: 1, port: 1, entry: 1, noerc: 1, harnessline: 1, comp: 2, sheet: 2, harness: 2, directive: 2, graphic: 3 };
export function schPick(X, Y) {
  const [x, y] = s2w(X, Y), tol = 3 / view.s; let best = -1, bp = 9;
  for (let i = S.prims.length - 1; i >= 0; i--) { const p = S.prims[i]; if (p.o < 0) continue; const b = p.bb;
    if (b && (x < b[0] - tol || x > b[2] + tol || y < b[1] - tol || y > b[3] + tol)) continue;
    if (!schHitPrim(p, x, y, tol)) continue; const pr = PRIORITY[S.objects[p.o].k] ?? 4; if (pr < bp) { bp = pr; best = p.o; if (pr === 0) break; } }
  if (best < 0) for (let i = 0; i < S.comps.length; i++) { const b = S.comps[i].b; if (b && x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]) { best = S.objects.findIndex(o => o.k === "comp" && o.comp === i); break; } }
  return best;
}
