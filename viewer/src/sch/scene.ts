// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { diffToMM } from "../board/scene";
import { MM, S } from "../core/state";
import { checkToMM } from "../review/check";
// ================================================================== schematic view (scene kind "schematic")
// A sheet drawn as Altium Designer draws it: the file's own colours and fonts on its paper, a line grid, a grey
// workspace around it. Units on the page are millimetres, Y downwards from the sheet's top-left corner.
export const SCH = { sel: -1, selNet: -1, selComp: -1, images: new Map(), byObj: null, filter: "" };
export const WORKSPACE = "#4a4d52", SEL = "#00b050";
export const isSch = () => !!(S && S.kind === "schematic");
export const MIL = 0.0254;
export function toMMsch(sc) {
  if (sc.mm) return sc; diffToMM(sc); checkToMM(sc);
  const f = v => v * MM, fb = b => b ? b.map(f) : b;
  for (const p of sc.prims) { if (p.p) p.p = p.p.map(f); if (p.b) p.b = p.b.map(f);
    for (const k of ["x", "y", "rx", "ry", "w", "m", "sz", "gw", "th"]) if (typeof p[k] === "number") p[k] = p[k] * MM;
    if (p.rr) p.rr = p.rr.map(f); p.bb = primBox(p); }
  for (const o of sc.objects) o.b = fb(o.b);
  for (const c of sc.comps) c.b = fb(c.b);
  for (const fo of sc.fonts) fo.emm = fo.em * MM;
  const sh = sc.sheet; for (const k of ["w", "h", "grid", "margin", "x0", "y0"]) if (typeof sh[k] === "number") sh[k] *= MM;
  sh.x0 = sh.x0 || 0; sh.y0 = sh.y0 || 0; sh.origin = sh.origin ? sh.origin.map(f) : [0, sh.h];
  if (sh.text === "stroke") sc.comps.forEach(c => { c.hidden = c.ref.startsWith("#"); });
  sc.bounds = sc.bounds.map(f); sc.mm = true; return sc;
}
export function primBox(p) {
  const w = (p.w || 0) / 2;
  if (p.k === "l" || p.k === "g" || p.k === "b") { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (let i = 0; i < p.p.length; i += 2) { x0 = Math.min(x0, p.p[i]); x1 = Math.max(x1, p.p[i]); y0 = Math.min(y0, p.p[i + 1]); y1 = Math.max(y1, p.p[i + 1]); }
    return [x0 - w, y0 - w, x1 + w, y1 + w]; }
  if (p.k === "r" || p.k === "x" || p.k === "i") return [p.b[0] - w, p.b[1] - w, p.b[2] + w, p.b[3] + w];
  if (p.k === "e" || p.k === "a") return [p.x - p.rx - w, p.y - p.ry - w, p.x + p.rx + w, p.y + p.ry + w];
  return null;   // texts: measured when drawn
}
