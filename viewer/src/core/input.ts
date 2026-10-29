// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { draw } from "../board/draw";
import { pick } from "../board/hit";
import { compInfo, select } from "../board/info";
import { buildTabs, stepCurrent } from "../board/tabs";
import { edgeClick, toggleEdge } from "../measure/edge-tool";
import { measureClick } from "../measure/measure";
import { snap } from "../measure/snap";
import { markClick } from "../panels/marks";
import { clearQuery } from "../panels/review";
import { schPick } from "../sch/hit";
import { crossProbe, schDouble, schFind } from "../sch/load";
import { shareNet } from "../sch/project-nets";
import { isSch } from "../sch/scene";
import { schSelect } from "../sch/select";
import { camPreset, set3D } from "../three/view3d";
import { $, esc, showInfo } from "./dom";
import { cv, S, st, view } from "./state";
import { fmtLen, setUnit, UNIT } from "./units";
import { fit, m, s2w } from "./viewport";
export function flip() { view.mirror = !view.mirror; $("bFlip").textContent = "View: " + (view.mirror ? "Bottom" : "Top"); draw(); }
export function toggle(key, btn) { st[key] = !st[key]; $(btn).classList.toggle("on", st[key]); if (key === "measure" && !st.measure) st.mpts = []; draw(); }
export function find(q) {
  q = q.trim().toLowerCase(); if (!q || !S) return;
  if (isSch()) { schFind(q); return; }
  const ci = S.comps.findIndex(c => c.ref.toLowerCase() === q);
  if (ci >= 0) { st.selComp = ci; st.selNet = -1; const b = S.comps[ci].bbox; if (b) fit([b[0] - 5, b[1] - 5, b[2] + 5, b[3] + 5]); showInfo(compInfo(ci)); draw(); return; }
  const ni = S.nets.findIndex(n => n.toLowerCase() === q);
  if (ni >= 0) { st.selNet = ni; st.selComp = -1; showInfo(`Net: <b>${esc(S.nets[ni])}</b>`); draw(); return; }
  showInfo(`Nothing named <b>${esc(q)}</b> on this board.`);
}
export function setSidebar(open) {
  $("app").classList.toggle("sidebar-open", open);
  $("bSidebar").setAttribute("aria-expanded", String(open));
}
$("bSidebar").onclick = () => setSidebar(!$("app").classList.contains("sidebar-open"));
$("b3d").onclick = () => set3D(!st.mode3d);
$("bFit").onclick = () => st.mode3d ? camPreset("iso") : fit();
$("bFlip").onclick = flip;
$("bMeasure").onclick = () => toggle("measure", "bMeasure");
$("bClear").onclick = () => { st.mpts = []; st.selOv = -1; if (isSch()) schSelect(-1); else select(null); };
export function zoomBy(f) { view.s = Math.min(Math.max(view.s * f, 0.2), 400); draw(); }
$("opac").oninput = e => { st.opac = e.target.value / 100; draw(); };
$("search").addEventListener("keydown", e => { if (e.key === "Enter") { find(e.target.value); e.target.blur(); } else if (e.key === "Escape") e.target.blur(); });
export let drag = null;
cv.addEventListener("mousedown", e => { if (document.activeElement && (document.activeElement as HTMLElement).blur) (document.activeElement as HTMLElement).blur();   // shortcuts follow the board
  drag = { x: e.offsetX, y: e.offsetY, cx: view.cx, cy: view.cy, moved: false }; });
window.addEventListener("mouseup", e => { if (!drag) return; const d = drag; drag = null;
  if (d.moved || e.target !== cv) return; const [x, y] = s2w(e.offsetX, e.offsetY);
  if (st.measure) { measureClick(e.offsetX, e.offsetY, e.altKey); return; }
  if (st.marking) { markClick(x, y); return; }
  if (st.edge && !isSch()) { edgeClick(e.offsetX, e.offsetY); return; }
  if (isSch()) schSelect(schPick(e.offsetX, e.offsetY)); else select(pick(e.offsetX, e.offsetY), [x, y]); });
cv.addEventListener("dblclick", e => { if (!S) return;
  if (isSch()) { schDouble(e.offsetX, e.offsetY); return; }
  const h = pick(e.offsetX, e.offsetY), ci = h ? h.pr[4] : -1; if (ci >= 0) crossProbe(S.comps[ci].ref, "schematic"); });
cv.addEventListener("contextmenu", e => { if (isSch()) e.preventDefault(); });
export function showCoord(x, y) {
  st.mouse = [x, y];
  if (!(st.measure && st.mpts.length)) $("coord").textContent = isSch()
    ? `X ${fmtLen(x - S.sheet.origin[0])}  Y ${fmtLen(S.sheet.origin[1] - y)} · grid ${fmtLen(S.sheet.grid)}` : `x ${fmtLen(x)}  y ${fmtLen(y)}`;
}
cv.addEventListener("mousemove", e => { if (!S) return; const [x, y] = s2w(e.offsetX, e.offsetY);
  showCoord(x, y);
  if (drag) { const dx = e.offsetX - drag.x, dy = e.offsetY - drag.y; if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    view.cx = drag.cx - m() * dx / view.s; view.cy = drag.cy - dy / view.s; draw(); }
  else if (st.measure) { st.mhover = snap(x, y, e.altKey); draw(); } });
cv.addEventListener("wheel", e => { e.preventDefault(); const [x, y] = s2w(e.offsetX, e.offsetY); const f = Math.exp(-e.deltaY * 0.0015);
  view.s = Math.min(Math.max(view.s * f, 0.2), 400); const [x2, y2] = s2w(e.offsetX, e.offsetY); view.cx += x - x2; view.cy += y - y2; draw(); }, { passive: false });
window.addEventListener("keydown", e => {
  const target = e.target;
  if (e.defaultPrevented || e.isComposing || e.ctrlKey || e.metaKey || e.altKey ||
      (target instanceof Element && (target.closest("input, select, textarea, dialog[open], #projectReview") || (target as HTMLElement).isContentEditable))) return;
  const k = e.key;
  if (k === "Escape" && matchMedia("(max-width:760px)").matches && $("app").classList.contains("sidebar-open")) {
    setSidebar(false); $("bSidebar").focus(); return;
  }
  if (!S || S.kind === "table") return;
  if (k === "q" || k === "Q") { setUnit(UNIT === "mm" ? "mil" : "mm"); return; }
  if ((k === "m" || k === "M") && e.shiftKey && !st.mode3d && !isSch()) { toggleEdge(); return; }
  if ((k === "m" || k === "M") && !st.mode3d) { toggle("measure", "bMeasure"); return; }
  if ((k === "n" || k === "N") && !st.mode3d) { toggle("marking", "bMark"); return; }
  if ((k === "x" || k === "X") && S.diff) { st.diff = !st.diff; draw(); return; }
  if ((k === "e" || k === "E") && S.check) { st.checks = !st.checks; draw(); return; }
  if (k === "Escape" && st.edge) { toggleEdge(); return; }
  if (k === "Escape" && st.marking) { toggle("marking", "bMark"); return; }
  if (k === "Escape" && (st.measure || st.mpts.length)) { st.mpts = []; st.mhover = null; if (st.measure) toggle("measure", "bMeasure"); return; }
  if (isSch()) { if (k === "f" || k === "F") fit(); else if (k === "Escape") { schSelect(-1); shareNet(null); }
    else if (k === "PageUp" || k === "PageDown") { e.preventDefault(); zoomBy(k === "PageUp" ? 1.25 : 0.8); } return; }
  if (k === "d" || k === "D") set3D(!st.mode3d);
  else if (k === "f" || k === "F") { if (st.mode3d) camPreset("iso"); else fit(); }
  else if (st.mode3d) return;
  else if ((k === "S" || k === "s") && e.shiftKey) { st.single = !st.single; buildTabs(); draw(); }
  else if (k === "+" || k === "=") stepCurrent(1); else if (k === "-" || k === "_") stepCurrent(-1);
  else if (k === "b" || k === "B") flip(); else if (k === "m" || k === "M") toggle("measure", "bMeasure");
  else if ((k === "C" || k === "c") && e.shiftKey) clearQuery();
  else if (k === "Escape") { st.mpts = []; st.selOv = -1; select(null); shareNet(null); } });
