// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the right dock (c0269, design decision 1)
// A third column of the page beside the drawing, never over it: the Properties tab (the inspector, #info) and,
// on boards and footprints, the Layers tab, which the 3D panel replaces in 3D. `I` collapses and opens it; its
// left edge resizes it between 240 and 480 px; both are kept in localStorage. At 760 px and below it is a bottom
// sheet of at most 60 % of the height that a selection opens and Esc or its close control dismisses.
import * as preact from "preact";
import { $ } from "../core/dom";
import { S, st } from "../core/state";
import { isSch } from "../sch/scene";
import { Icon } from "../ui/icons";
import { buildLayers } from "./layers";
import { refreshToolbar } from "./toolbar";
import { build3DPanel } from "./view3d-panel";

const store = (key, fallback) => { try { return localStorage.getItem(key) ?? fallback; } catch (e) { return fallback; } };
const keep = (key, value) => { try { localStorage.setItem(key, value); } catch (e) { /* kept for this page only */ } };
export const DOCK = { open: store("fenolite.view.dock", "open") !== "closed", width: Math.min(480, Math.max(240, +store("fenolite.view.dockWidth", "320") || 320)),
  tab: "props", sheet: false };
export const dockNarrow = () => matchMedia("(max-width:760px)").matches;
export const layersApply = () => !!S && !S.kind && !isSch();   // a board or a footprint item
export function DockHead() {
  const second = layersApply() ? (st.mode3d ? ["3d", "3D view", "cube"] : ["layers", "Layers", "layers"]) : null;
  const tabs = [["props", "Properties", "sliders"], ...(second ? [second] : [])];
  if (!tabs.some(t => t[0] === DOCK.tab)) DOCK.tab = "props";
  return <>
    <div class="dockTabs" role="tablist" aria-label="Inspector">
      {tabs.map(([id, title, icon]) => <button type="button" role="tab" id={`dockTab_${id}`} aria-selected={DOCK.tab === id}
        aria-controls={id === "props" ? "dockProps" : id === "layers" ? "dockLayers" : "dock3d"} class="dockTab" onClick={() => setDockTab(id)}>
        <Icon name={icon} size={14} /><span>{title}</span></button>)}
    </div>
    <button type="button" id="dockClose" class="tb icon small ghost" aria-label={dockNarrow() ? "Close the inspector" : "Hide the inspector"}
      data-tip={dockNarrow() ? "Close" : "Hide the inspector"} data-keys={dockNarrow() ? "Esc" : "I"} onClick={() => dockNarrow() ? closeSheet() : setDock(false)}>
      <Icon name={dockNarrow() ? "x" : "dock"} size={14} /></button>
  </>;
}
export function refreshDock() {
  const app = $("app");
  app.classList.toggle("dock-closed", !DOCK.open); app.classList.toggle("dock-sheet-open", DOCK.sheet);
  app.style.setProperty("--dock-w", `${DOCK.width}px`);
  preact.render(<DockHead />, $("dockHead"));
  $("dockProps").hidden = DOCK.tab !== "props"; $("dockLayers").hidden = DOCK.tab !== "layers"; $("dock3d").hidden = DOCK.tab !== "3d";
  if (DOCK.tab === "layers") buildLayers(); else if (DOCK.tab === "3d") build3DPanel();
}
export function setDockTab(id) { DOCK.tab = id; refreshDock(); }
export function setDock(open) { DOCK.open = open; keep("fenolite.view.dock", open ? "open" : "closed"); refreshDock(); refreshToolbar(); }
export function toggleDock() { if (dockNarrow()) { if (DOCK.sheet) closeSheet(); else openSheet(); } else setDock(!DOCK.open); }
export function openSheet() { DOCK.sheet = true; refreshDock(); }
export function closeSheet() { if (!DOCK.sheet) return false; DOCK.sheet = false; refreshDock(); return true; }
export function dockShowSelection() {   // a selection shows the Properties tab; in a narrow window it opens the sheet
  let changed = false;
  if (DOCK.tab !== "props") { DOCK.tab = "props"; changed = true; }
  if (dockNarrow() && !DOCK.sheet) { DOCK.sheet = true; changed = true; }
  if (changed) refreshDock();
}
// The resize handle: a pointer drag on the dock's left edge, or the arrow keys on it.
function setWidth(w) { DOCK.width = Math.round(Math.min(480, Math.max(240, w))); $("app").style.setProperty("--dock-w", `${DOCK.width}px`); keep("fenolite.view.dockWidth", String(DOCK.width)); }
$("dockResize").addEventListener("pointerdown", (e: PointerEvent) => {
  if (dockNarrow()) return; e.preventDefault(); const grip = e.currentTarget as HTMLElement, x0 = e.clientX, w0 = DOCK.width;
  grip.setPointerCapture(e.pointerId); grip.classList.add("on");
  const move = (m: PointerEvent) => setWidth(w0 + x0 - m.clientX);
  const up = () => { grip.classList.remove("on"); grip.removeEventListener("pointermove", move); grip.removeEventListener("pointerup", up); };
  grip.addEventListener("pointermove", move); grip.addEventListener("pointerup", up);
});
$("dockResize").addEventListener("keydown", (e: KeyboardEvent) => {
  if (e.key === "ArrowLeft" || e.key === "ArrowRight") { e.preventDefault(); setWidth(DOCK.width + (e.key === "ArrowLeft" ? 16 : -16)); }
});
matchMedia("(max-width:760px)").addEventListener?.("change", () => { DOCK.sheet = false; refreshDock(); });
