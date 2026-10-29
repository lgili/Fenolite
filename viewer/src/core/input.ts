// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { draw } from "../board/draw";
import { pick } from "../board/hit";
import { compInfo, select } from "../board/info";
import { edgeClick } from "../measure/edge-tool";
import { measureClick } from "../measure/measure";
import { snap } from "../measure/snap";
import { markClick } from "../panels/marks";
import { refreshToolbar } from "../panels/toolbar";
import { schPick } from "../sch/hit";
import { crossProbe, schDouble, schFind } from "../sch/load";
import { isSch } from "../sch/scene";
import { schSelect } from "../sch/select";
import { openPalette } from "../dialogs/palette";
import { commandForKey, IS_MAC } from "./commands";
import { $, esc, showInfo } from "./dom";
import { cv, S, st, view } from "./state";
import { fmtLen } from "./units";
import { fit, m, s2w } from "./viewport";
import { netModel, partModel } from "../inspect/model";
import { inspect } from "../panels/inspector";
export function flip() { view.mirror = !view.mirror; refreshToolbar(); draw(); }
export function toggle(key) { st[key] = !st[key]; if (key === "measure" && !st.measure) st.mpts = []; refreshToolbar(); draw(); }
export function find(q) {
  q = q.trim().toLowerCase(); if (!q || !S) return;
  if (isSch()) { schFind(q); return; }
  const ci = S.comps.findIndex(c => c.ref.toLowerCase() === q);
  if (ci >= 0) { st.selComp = ci; st.selNet = -1; const b = S.comps[ci].bbox; if (b) fit([b[0] - 5, b[1] - 5, b[2] + 5, b[3] + 5]); inspect(() => partModel(ci)); draw(); return; }
  const ni = S.nets.findIndex(n => n.toLowerCase() === q);
  if (ni >= 0) { st.selNet = ni; st.selComp = -1; inspect(() => netModel(ni)); draw(); return; }
  showInfo(`Nothing named <b>${esc(q)}</b> on this board.`);
}
export function setSidebar(open) {
  $("app").classList.toggle("sidebar-open", open);
  refreshToolbar();
}
export function zoomBy(f) { view.s = Math.min(Math.max(view.s * f, 0.2), 400); draw(); }
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
    ? `X ${fmtLen(x - S.sheet.origin[0])}   Y ${fmtLen(S.sheet.origin[1] - y)}` : `X ${fmtLen(x)}   Y ${fmtLen(y)}`;
}
cv.addEventListener("mousemove", e => { if (!S) return; const [x, y] = s2w(e.offsetX, e.offsetY);
  showCoord(x, y);
  if (drag) { const dx = e.offsetX - drag.x, dy = e.offsetY - drag.y; if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    view.cx = drag.cx - m() * dx / view.s; view.cy = drag.cy - dy / view.s; draw(); }
  else if (st.measure) { st.mhover = snap(x, y, e.altKey); draw(); } });
cv.addEventListener("wheel", e => { e.preventDefault(); const [x, y] = s2w(e.offsetX, e.offsetY); const f = Math.exp(-e.deltaY * 0.0015);
  view.s = Math.min(Math.max(view.s * f, 0.2), 400); const [x2, y2] = s2w(e.offsetX, e.offsetY); view.cx += x - x2; view.cy += y - y2; draw(); }, { passive: false });
// The shortcuts (c0235, c0268): looked up in the command registry, never in form controls, dialogs or the project
// review, during composition, after default prevention or with Ctrl, Meta or Alt; the one exception is the
// palette chord, Ctrl+K (Cmd+K on macOS), which also works from a focused field.
window.addEventListener("keydown", e => {
  if (e.defaultPrevented || e.isComposing) return;
  if ((IS_MAC ? e.metaKey : e.ctrlKey) && !e.altKey && !e.shiftKey && (e.key === "k" || e.key === "K")) { e.preventDefault(); openPalette(); return; }
  const target = e.target;
  if (e.ctrlKey || e.metaKey || e.altKey ||
      (target instanceof Element && (target.closest("input, select, textarea, dialog[open], #projectReview") || (target as HTMLElement).isContentEditable))) return;
  const c = commandForKey(e); if (!c) return;
  if (c.keys.includes("PageUp") || c.keys.includes("PageDown")) e.preventDefault();
  c.run(); refreshToolbar();
});
