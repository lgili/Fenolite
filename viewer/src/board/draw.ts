// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { $ } from "../core/dom";
import { linkLater } from "../core/links";
import { ctx, cv, S, st, view, vis } from "../core/state";
import { worldTf } from "../core/viewport";
import { drawEdge } from "../measure/edge-tool";
import { drawMeasure } from "../measure/measure";
import { drawMarks } from "../panels/marks";
import { HL_ALPHA } from "../panels/review";
import { refreshStatus } from "../panels/status-bar";
import { drawCheck } from "../review/check";
import { drawRoles, paintRoleCopper } from "../roles/draw";
import { drawSch } from "../sch/draw";
import { cache, compCache, netCache, qCache, selCache, textCache } from "./cache";
import { drawDiff } from "./diff";
import { boardPath } from "./geometry";
import { drawOverlays } from "./overlays";
import { drawVariantMarks, notFitted, VARIANT } from "./variants";
export const VIEWL = id => id.startsWith("View.");
export function activeSide() { return view.mirror ? "bottom" : "top"; }
export function order() {
  const L = S.layers.filter(l => vis.get(l.id));
  if (st.single) return L.filter(l => l.id === st.cur || l.id === "View.Drill" || l.id === "View.Outline").map(l => [l, 1]);
  const act = activeSide(), other = act === "top" ? "bottom" : "top";
  const both = L.filter(l => l.side === "both" && !VIEWL(l.id)), oth = L.filter(l => l.side === other), actL = L.filter(l => l.side === act), post = L.filter(l => VIEWL(l.id));
  if (act === "bottom") actL.reverse();
  let out = [...oth.map(l => [l, st.opac]), ...both.map(l => [l, 1]), ...actL.map(l => [l, 1]), ...post.map(l => [l, 1])];
  const ci = out.findIndex(e => e[0].id === st.cur); if (ci >= 0) { const [e] = out.splice(ci, 1); e[1] = 1; out.splice(out.length - post.length, 0, e); }
  return out;
}
export function paintCache(g, c, lid, color, alpha, unit) {
  if (!c || !c.n) return;
  g.globalAlpha = alpha;
  if (lid === "View.Drill") { g.fillStyle = color; g.fill(c.fill, "nonzero"); g.strokeStyle = color; g.lineCap = "round"; for (const [w, p] of c.strokes) { g.lineWidth = Math.max(w, 1 / unit); g.stroke(p); } return; }
  g.fillStyle = color; g.fill(c.fill, "evenodd");
  g.strokeStyle = color; g.lineCap = "round"; g.lineJoin = "round";
  for (const [w, p] of c.strokes) { g.lineWidth = Math.max(w, 1 / unit); g.stroke(p); }
  if (lid === "View.ZoneOutline" || lid === "View.ZoneEdge") g.setLineDash([6 / unit, 4 / unit]);
  g.lineWidth = 1 / unit; g.stroke(c.outline); g.setLineDash([]);
  if (c.hb[2] >= c.hb[0]) { const [x0, y0, x1, y1] = c.hb, step = 8 / unit;   // hatched rings: 45° lines inside, a solid edge
    g.save(); g.clip(c.hatch, "evenodd"); g.lineWidth = 1 / unit; g.beginPath();
    for (let t = x0 - (y1 - y0); t <= x1; t += step) { g.moveTo(t, y0); g.lineTo(t + (y1 - y0), y1); } g.stroke(); g.restore();
    g.lineWidth = 1.5 / unit; g.stroke(c.hatch); }
}
export function paintTexts(g, lid, color, alpha, unit) {
  const tc = textCache.get(lid); if (!tc || !tc.n) return;
  g.globalAlpha = alpha; g.strokeStyle = color; g.lineCap = "round"; g.lineJoin = "round";
  for (const [w, p] of tc.strokes) { g.lineWidth = Math.max(w, 0.6 / unit); g.stroke(p); }
}
// ---- net emphasis (c0301, design decision 4): a picked net, part or filter result is drawn in its own layer
// colours at full opacity with a 1.5 px outline in the --emphasis token, never lightened; its zone fills at 0.55
// with the outline, so its tracks and pads stay readable over its pour. The rest dims by the highlight mode.
let EMPHASIS = "", EMPHASIS_KEY = "";
export function emphasisColor() {   // the --emphasis token, read again when the theme changes
  const key = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: light)").matches ? "l" : "d");
  if (!EMPHASIS || key !== EMPHASIS_KEY) { EMPHASIS_KEY = key; EMPHASIS = getComputedStyle(document.documentElement).getPropertyValue("--emphasis").trim() || "#ffffff"; }
  return EMPHASIS;
}
export const ZONE_FILL_ALPHA = 0.55;
export const isZoneFill = pr => pr[1] === "p" && pr[4] < 0 && pr[3] >= 0;
export function paintEmphasis(g, c, lid, color, unit, zone) {
  if (!c || !c.n) return;
  if (VIEWL(lid)) { paintCache(g, c, lid, color, 1, unit); return; }
  const em = emphasisColor(), w = 1.5 / unit;
  g.globalAlpha = 1; g.strokeStyle = em; g.lineCap = "round"; g.lineJoin = "round";
  if (zone) { paintCache(g, c, lid, color, ZONE_FILL_ALPHA, unit); g.globalAlpha = 1; g.strokeStyle = em; g.lineWidth = w; g.stroke(c.fill); return; }
  g.lineWidth = 2 * w; g.stroke(c.fill);   // the outline: half of it under the fill, half outside
  for (const [sw, p] of c.strokes) { g.lineWidth = Math.max(sw, 1 / unit) + 2 * w; g.stroke(p); }
  paintCache(g, c, lid, color, 1, unit);
}
export function paintPicked(map, key, test, ord) {   // the zone fills of the pick first, then the rest on top
  const zones = selCache(map, "z:" + key, pr => test(pr) && isZoneFill(pr)), rest = selCache(map, key, pr => test(pr) && !isZoneFill(pr));
  for (const [l] of ord) paintEmphasis(ctx, zones.get(l.id), l.id, l.color, view.s, true);
  for (const [l] of ord) paintEmphasis(ctx, rest.get(l.id), l.id, l.color, view.s, false);
}
export function draw() {
  if (S && S.kind === "table") return;
  if (S && S.kind === "schematic") return drawSch();
  if (!S || st.mode3d) return;
  const th = S.theme || {};
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.fillStyle = th.background || "#15171b"; ctx.fillRect(0, 0, cv.width, cv.height);
  worldTf(); ctx.globalAlpha = 1; ctx.fillStyle = th.board || "#050505"; ctx.fill(boardPath(), "evenodd");
  const qy = st.query && st.query.prims.size ? st.query : null, picked = st.selNet >= 0 || st.selComp >= 0;
  const ord = order(), sel = picked || !!qy, other = HL_ALPHA[st.hl] ?? HL_ALPHA.dim;
  const dim = S.diff && st.diff && S.diff.kind === "board" ? 0.35 : 1;   // c0184: the board steps back while the changes are shown
  for (const [l, a00] of ord) { const a0 = a00 * dim, a = a0 * (l.alpha ?? 1); paintCache(ctx, cache.get(l.id), l.id, l.color, sel ? a * other : a, view.s);
    if (view.s * 0.4 > 1) paintTexts(ctx, l.id, l.color, sel ? a * other : a, view.s); }
  paintRoleCopper(ord, (sel ? other : 1) * dim);   // c0305: role copper in its role colour, under a pick's emphasis
  if (qy) { paintPicked(qCache, qy.text, pr => qy.prims.has(pr), ord);
    ctx.globalAlpha = 1; ctx.strokeStyle = emphasisColor(); ctx.lineWidth = 1 / view.s;
    for (const ci of qy.comps.slice(0, 2000)) { const b = S.comps[ci].bbox; if (b) ctx.strokeRect(b[0] - 0.2, b[1] - 0.2, b[2] - b[0] + 0.4, b[3] - b[1] + 0.4); } }
  if (picked) {
    if (st.selNet >= 0) paintPicked(netCache, st.selNet, pr => pr[3] === st.selNet, ord); else paintPicked(compCache, st.selComp, pr => pr[4] === st.selComp, ord);
    if (st.selComp >= 0 && S.comps[st.selComp].bbox) { const b = S.comps[st.selComp].bbox; ctx.globalAlpha = 1; ctx.strokeStyle = emphasisColor();
      ctx.lineWidth = 1.5 / view.s; ctx.setLineDash([5 / view.s, 3 / view.s]); ctx.strokeRect(b[0] - 0.3, b[1] - 0.3, b[2] - b[0] + 0.6, b[3] - b[1] + 0.6); ctx.setLineDash([]); }
  }
  if (VARIANT && S.variants) { worldTf(); ctx.globalAlpha = 0.6; ctx.fillStyle = (S.theme || {}).board || "#050505";
    for (const c of S.comps) if (c.bbox && notFitted(c.ref)) { const b = c.bbox; ctx.fillRect(b[0], b[1], b[2] - b[0], b[3] - b[1]); }
    drawVariantMarks(S.comps.map(c => [c.ref, c.bbox])); }
  drawDiff(); drawOverlays(); drawCheck(); drawRoles(); drawEdge(); drawMarks(); drawMeasure(); linkLater();
  $("zoomv").textContent = `Zoom ${view.s.toFixed(1)} px/mm`; refreshStatus();
}
