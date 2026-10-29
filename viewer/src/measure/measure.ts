// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { draw } from "../board/draw";
import { $ } from "../core/dom";
import { ctx, st, view } from "../core/state";
import { fmtLen } from "../core/units";
import { dpr, s2w, w2s, worldTf } from "../core/viewport";
import { snap } from "./snap";
export function drawMeasure() {
  if (!st.measure && !st.mpts.length) return; worldTf(); ctx.globalAlpha = 1; const C = "#00e08a"; ctx.strokeStyle = C; ctx.lineWidth = 1.5 / view.s;
  const mark = (q, on) => { const r = 4 / view.s; ctx.strokeRect(q[0] - r, q[1] - r, 2 * r, 2 * r); if (on) { ctx.beginPath(); ctx.moveTo(q[0] - 2 * r, q[1]); ctx.lineTo(q[0] + 2 * r, q[1]); ctx.moveTo(q[0], q[1] - 2 * r); ctx.lineTo(q[0], q[1] + 2 * r); ctx.stroke(); } };
  if (st.mhover) { mark(st.mhover.p, st.mhover.snapped); if (st.mhover.edge && !st.mpts.length) $("coord").textContent = `snap: ${st.mhover.edge}`; }
  if (!st.mpts.length) return;
  const a = st.mpts[0], b = st.mpts[1] || (st.mhover && st.mhover.p); mark(a, true); if (!b) return;
  ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); if (st.mpts[1]) mark(b, true);
  const d = Math.hypot(b[0] - a[0], b[1] - a[1]), txt = `${fmtLen(d)}   Δx ${fmtLen(Math.abs(b[0] - a[0]))}   Δy ${fmtLen(Math.abs(b[1] - a[1]))}`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0); const P = w2s(b[0], b[1]); ctx.font = "600 13px system-ui"; const w = ctx.measureText(txt).width;
  ctx.fillStyle = "#000c"; ctx.fillRect(P[0] + 8, P[1] - 28, w + 12, 20); ctx.fillStyle = C; ctx.fillText(txt, P[0] + 14, P[1] - 13); worldTf();
  $("coord").textContent = `measure: ${txt}`;
}
export function measureClick(X, Y, free) { const [x, y] = s2w(X, Y), q = snap(x, y, free).p; if (st.mpts.length >= 2) st.mpts = []; st.mpts.push(q); draw(); }
