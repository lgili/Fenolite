// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== net roles drawn on the board (c0273)
// paintRoleCopper: the copper of each role net in its role colour, over the board and under a picked net's
// emphasis (signal nets stay as they are). drawRoles, after the check markers: hot loops hatched at 45° and gate
// loops at 135° through their pads with their name and area, Kelvin pairs as dashed sense lines from the
// element's pads to the receiver's, and the role findings as rings of their severity. Each overlay has its own
// hatch or dash, and the legend names every colour, so colour is never the only cue.
import { selCache } from "../board/cache";
import { paintCache } from "../board/draw";
import { ctx, P2D, S, view } from "../core/state";
import { fmtArea } from "../inspect/model";
import { dpr, w2s, worldTf } from "../core/viewport";
import { SEV_COLOR } from "../review/check";
import { GROUP_KIND, ROLE_GLYPH, ROLE_SEL, ROLE_VIEW, roleColor, rolesData } from "./roles";

export let roleCache = new Map();
const HALO = "#000000", LABEL_ZOOM = 12;   // labels of the groups from 12 px/mm, or of the selected one
export function resetRoleCache() { roleCache = new Map(); }
const copper = l => l.kind === "copper" || /\.Cu$/.test(l.id);
export function paintRoleCopper(ord, alpha) {
  const R = rolesData(); if (!R || !ROLE_VIEW.colors) return;
  for (const row of R.roles) {
    if (row.net_index < 0 || row.kind === "signal") continue;
    const m = selCache(roleCache, row.net_index, pr => pr[3] === row.net_index), color = roleColor(row.kind);
    for (const [l, a] of ord) if (copper(l)) paintCache(ctx, m.get(l.id), l.id, color, Math.min(1, a) * alpha, view.s);
  }
}
function hatch(pts, angle, color, sel) {   // the polygon through the points, hatched at `angle` degrees, its outline solid
  const u = 1 / view.s, path = new P2D(); pts.forEach((p, k) => k ? path.lineTo(p[0], p[1]) : path.moveTo(p[0], p[1])); path.closePath();
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]), x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys), d = Math.max(x1 - x0, y1 - y0);
  ctx.save(); ctx.clip(path); ctx.beginPath();
  const step = 7 * u, dir = angle === 45 ? 1 : -1;
  for (let t = -d; t <= 2 * d; t += step) { ctx.moveTo(x0 + t, y0); ctx.lineTo(x0 + t - dir * d, y0 + d); }
  ctx.globalAlpha = 0.55; ctx.strokeStyle = HALO; ctx.lineWidth = 2.6 * u; ctx.stroke();   // a dark halo: the hatch reads on its own role's copper
  ctx.globalAlpha = 0.95; ctx.strokeStyle = color; ctx.lineWidth = 1.2 * u; ctx.stroke(); ctx.restore();
  ctx.lineJoin = "round"; ctx.globalAlpha = 0.6; ctx.strokeStyle = HALO; ctx.lineWidth = (sel ? 5 : 3.6) * u; ctx.stroke(path);
  ctx.globalAlpha = 1; ctx.strokeStyle = color; ctx.lineWidth = (sel ? 3 : 1.8) * u; ctx.stroke(path);
}
function label(x, y, text, color) {   // a small pill in screen pixels at a world point
  ctx.save(); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); const [X, Y] = w2s(x, y);
  ctx.font = "600 11px system-ui, sans-serif"; const w = ctx.measureText(text).width;
  ctx.globalAlpha = 0.9; ctx.fillStyle = "#101216"; ctx.fillRect(X - w / 2 - 5, Y - 9, w + 10, 18);
  ctx.globalAlpha = 1; ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.strokeRect(X - w / 2 - 5, Y - 9, w + 10, 18);
  ctx.fillStyle = "#f2f4f7"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(text, X, Y + 0.5); ctx.restore();
}
export function drawRoles() {
  const R = rolesData(); if (!R || (S && S.kind)) return; worldTf(); ctx.globalAlpha = 1;
  const u = 1 / view.s, labels = [];
  R.groups.forEach((g, i) => {
    const pts = g.points || [], sel = i === ROLE_SEL.group, color = roleColor(GROUP_KIND[g.type]);
    if (g.type === "kelvin") {
      if (!ROLE_VIEW.kelvin || pts.length < 4) return;
      const n = pts.length / 2, el = pts.slice(0, n), rx = pts.slice(n);
      ctx.strokeStyle = color; ctx.lineWidth = (sel ? 2.6 : 1.6) * u; ctx.setLineDash([4 * u, 3 * u]); ctx.beginPath();
      el.forEach((p, k) => { const q = rx[k] || rx[rx.length - 1]; ctx.moveTo(p[0], p[1]); ctx.lineTo(q[0], q[1]); }); ctx.stroke(); ctx.setLineDash([]);
      for (const p of el) { ctx.beginPath(); ctx.arc(p[0], p[1], 4 * u, 0, 2 * Math.PI); ctx.stroke(); }
      const c = el.reduce((a, p) => [a[0] + p[0] / el.length, a[1] + p[1] / el.length], [0, 0]);
      if (sel || view.s >= LABEL_ZOOM) labels.push([c[0], c[1] - 8 * u, `${ROLE_GLYPH.kelvin} ${g.name}`, color]);
      return;
    }
    if (!ROLE_VIEW.loops || pts.length < 3) return;
    hatch(pts, g.type === "hot" ? 45 : 135, color, sel);
    const c = pts.reduce((a, p) => [a[0] + p[0] / pts.length, a[1] + p[1] / pts.length], [0, 0]);
    const area = g.area_nm2 != null ? ` · ${fmtArea(g.area_nm2 / 1e12)}` : "";
    if (sel || view.s >= LABEL_ZOOM) labels.push([c[0], c[1], `${g.type === "hot" ? "⟲" : "⟳"} ${g.name}${area}`, color]);
  });
  if (ROLE_VIEW.findings) drawRoleFindings(R, u);
  for (const [x, y, text, color] of labels) label(x, y, text, color);   // on top of the markers
}
function drawRoleFindings(R, u) {
  worldTf();
  for (let i = R.findings.length - 1; i >= 0; i--) { const x = R.findings[i]; if (!x.at) continue;
    const sel = i === ROLE_SEL.finding, r = (sel ? 9 : 6) * u, [cx, cy] = x.at;
    ctx.globalAlpha = 1; ctx.strokeStyle = SEV_COLOR[x.severity] || "#cccccc"; ctx.lineWidth = (sel ? 2.5 : 1.6) * u;
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI); ctx.moveTo(cx - r * 0.5, cy - r * 0.5); ctx.lineTo(cx + r * 0.5, cy + r * 0.5); ctx.moveTo(cx + r * 0.5, cy - r * 0.5); ctx.lineTo(cx - r * 0.5, cy + r * 0.5); ctx.stroke();
    if (sel && x.box && (x.box[2] > x.box[0] || x.box[3] > x.box[1])) { const b = x.box, e = 2 * u; ctx.setLineDash([5 * u, 3 * u]);
      ctx.strokeRect(b[0] - e, b[1] - e, b[2] - b[0] + 2 * e, b[3] - b[1] + 2 * e); ctx.setLineDash([]); } }
}
