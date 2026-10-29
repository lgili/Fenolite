// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== review tools (c0189): edge measure, links, marks, SVG, print
import { addPrim, byLayer, newCache } from "../board/cache";
import { draw, paintCache } from "../board/draw";
import { pick } from "../board/hit";
import { $, esc, showInfo } from "../core/dom";
import { ctx, st, view } from "../core/state";
import { fmtLen } from "../core/units";
import { dpr, w2s, worldTf } from "../core/viewport";
import { refreshToolbar } from "../panels/toolbar";
import { edgeBetween } from "./edge";
export const EDGE_C = "#00d0ff";
export function toggleEdge() { st.edge = !st.edge; st.epick = []; st.eres = null; refreshToolbar(); draw(); }
export function edgeGroup(h) {   // every primitive of the clicked item on its layer: a pad's core and its edge stroke together
  const pr = h.pr; if (!pr[5]) return [pr];
  return (byLayer.get(h.layer.id) || []).map(e => e[0]).filter(q => q[5] === pr[5] && q[4] === pr[4] && q[1] !== "t");
}
export function edgeClick(X, Y) {
  const h = pick(X, Y); if (!h) return;
  if (st.epick.length >= 2) { st.epick = []; st.eres = null; }
  st.epick.push({ name: h.pr[5] || h.layer.name, layer: h.layer, prims: edgeGroup(h) });
  if (st.epick.length === 2) { const [a, b] = st.epick; st.eres = edgeBetween(a.prims, b.prims);
    if (st.eres) showInfo(`<b>Edge to edge: ${fmtLen(st.eres.d)}</b><br>${esc(a.name)} (${esc(a.layer.name)}) ↔ ${esc(b.name)} (${esc(b.layer.name)})` +
      (a.layer.id !== b.layer.id ? "<br><i>Two layers: the distance is measured in the plane.</i>" : "")); }
  draw();
}
export function drawEdge() {
  if (!st.edge && !st.eres) return; worldTf(); ctx.globalAlpha = 0.9;
  for (const g of st.epick) { const c = newCache(); for (const pr of g.prims) addPrim(c, pr); paintCache(ctx, c, g.layer.id, EDGE_C, 0.55, view.s); }
  const r = st.eres; if (!r) return; ctx.globalAlpha = 1; ctx.strokeStyle = ctx.fillStyle = EDGE_C; ctx.lineWidth = 1.5 / view.s;
  ctx.beginPath(); ctx.moveTo(r.a[0], r.a[1]); ctx.lineTo(r.b[0], r.b[1]); ctx.stroke();
  for (const q of [r.a, r.b]) { ctx.beginPath(); ctx.arc(q[0], q[1], 3 / view.s, 0, 2 * Math.PI); ctx.fill(); }
  const txt = `edge ${fmtLen(r.d)}`; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); const P = w2s(r.b[0], r.b[1]); ctx.font = "600 13px system-ui"; const w = ctx.measureText(txt).width;
  ctx.fillStyle = "#000c"; ctx.fillRect(P[0] + 8, P[1] + 6, w + 12, 20); ctx.fillStyle = EDGE_C; ctx.fillText(txt, P[0] + 14, P[1] + 21); worldTf();
  $("coord").textContent = `measure: ${txt}`;
}
