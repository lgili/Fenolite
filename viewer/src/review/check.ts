// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { draw } from "../board/draw";
import { layerName } from "../board/info";
import { buildTabs } from "../board/tabs";
import { esc, showInfo } from "../core/dom";
import { MM, S, ctx, st, view, vis } from "../core/state";
import { fit, worldTf } from "../core/viewport";
import { buildMessages } from "../panels/messages";
import { isSch } from "../sch/scene";
import { set3D } from "../three/view3d";
import { $ } from "../core/dom";
// ================================================================== check findings (c0188)
export const SEV_COLOR = { error: "#ff4040", warning: "#ffb020", info: "#4da3ff" };
export function checkToMM(sc) { const C = sc.check; if (!C || C.mm) return; C.mm = true; const f = v => v * MM;
  for (const x of C.findings) { if (x.at) x.at = x.at.map(f); if (x.box) x.box = x.box.map(f); } }
export function drawCheck() {   // a ring with four ticks at each placed finding, the colour of its severity; the box of the one chosen
  const C = S.check; if (!C || !st.checks) return; if (!isSch()) worldTf(); ctx.globalAlpha = 1;
  for (let i = C.findings.length - 1; i >= 0; i--) { const x = C.findings[i];   // errors last, on top
    if (!x.at || (x.layer && vis.has(x.layer) && !vis.get(x.layer))) continue;
    const sel = i === st.selFinding, r = (sel ? 9 : 6) / view.s, [cx, cy] = x.at;
    ctx.strokeStyle = SEV_COLOR[x.severity] || "#cccccc"; ctx.lineWidth = (sel ? 2.5 : 1.6) / view.s; ctx.beginPath(); ctx.arc(cx, cy, r, 0, 2 * Math.PI);
    for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) { ctx.moveTo(cx + dx * r * 0.6, cy + dy * r * 0.6); ctx.lineTo(cx + dx * r * 1.6, cy + dy * r * 1.6); }
    ctx.stroke();
    if (sel && x.box && (x.box[2] > x.box[0] || x.box[3] > x.box[1])) { const b = x.box, e = 2 / view.s; ctx.setLineDash([5 / view.s, 3 / view.s]);
      ctx.strokeRect(b[0] - e, b[1] - e, b[2] - b[0] + 2 * e, b[3] - b[1] + 2 * e); ctx.setLineDash([]); } }
}
export function selectFinding(i) {
  const x = S.check.findings[i]; st.selFinding = i; if (st.mode3d) set3D(false);
  if (x.layer && !isSch() && S.layers.some(l => l.id === x.layer)) { st.cur = x.layer; vis.set(x.layer, true); buildTabs(); }   // its layer, current
  if (x.at) { const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]], m = Math.max(b[2] - b[0], b[3] - b[1], isSch() ? 10 : 6) * 0.8; fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); }
  showInfo(`<b>${esc(x.code)}</b> · ${esc(x.severity)}<br>${esc(x.message)}` + (x.where ? `<br>Where: ${esc(x.where)}` : "") +
    (x.layer && !isSch() ? `<br>Layer: ${esc(layerName(x.layer))}` : "") + (x.at ? "" : "<br><i>No position on this document.</i>") +
    `<br>Stage: ${esc(x.stage || "?")} · evidence ${esc(x.evidence || "?")}`);
  if (S.project_review?.binding && !S.project_review.binding.matched) $("info").innerHTML += `<br><b>Historical report:</b> ${esc(S.project_review.binding.note)}`;
  buildMessages(); draw();
}
