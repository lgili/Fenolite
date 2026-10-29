// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== layers: order, current layer, presets
// The layers of a board are listed in the dock's Layers panel (c0269, panels/layers); the bottom bar keeps the
// sheet tabs of a schematic only. buildTabs() keeps its name: it refreshes the panel and the status bar.
import { $ } from "../core/dom";
import { S, st, vis } from "../core/state";
import { buildLayers } from "../panels/layers";
import { draw, VIEWL } from "./draw";
export const TAB_ORDER = id => { const k = id.endsWith(".Cu") ? (id === "F.Cu" ? 0 : id === "B.Cu" ? 2 : 1) : id.startsWith("Mech") ? 3 : id.endsWith("SilkS") ? 4 : id.endsWith("Paste") ? 5 : id.endsWith("Mask") ? 6
  : id.endsWith("CrtYd") ? 7 : id.endsWith("Fab") ? 8 : id === "Edge.Cuts" ? 9 : id.startsWith("View.") ? 11 : 10; return k; };
export function tabLayers() { return [...S.layers].sort((a, b) => (a.tab ?? TAB_ORDER(a.id) * 100) - (b.tab ?? TAB_ORDER(b.id) * 100) || (a.id.startsWith("B.") - b.id.startsWith("B.")) || a.id.localeCompare(b.id, undefined, { numeric: true })); }
export function buildTabs() {
  buildLayers();
  const cur = S.layers.find(l => l.id === st.cur); $("cur").textContent = cur ? `Layer ${cur.name}${st.single ? " · only this layer" : ""}` : "";
}
export function setCurrent(id) { st.cur = id; vis.set(id, true); buildTabs(); draw(); }
export function stepCurrent(dir) { const L = tabLayers().filter(l => vis.get(l.id)); if (!L.length) return; let i = L.findIndex(l => l.id === st.cur); i = (i + dir + L.length) % L.length; setCurrent(L[i].id); }
export const SETS = { "All layers": () => true, "Signal layers": l => l.kind === "copper" || VIEWL(l.id), "Top side": l => l.side !== "bottom", "Bottom side": l => l.side !== "top", "Default": l => l.visible };
export function applyPreset(name) {   // a layer set of the presets menu, or the current layer alone (Shift+S)
  if (name === "Current layer only") st.single = !st.single;
  else { st.single = false; for (const l of S.layers) vis.set(l.id, SETS[name](l)); }
  buildTabs(); draw();
}
$("ls").onclick = e => { e.stopPropagation(); const mnu = $("lsmenu"); mnu.innerHTML = "";
  for (const name of [...Object.keys(SETS), "Current layer only"]) { const d = document.createElement("button"); d.type = "button"; d.className = "menuItem";
    d.setAttribute("role", "menuitem"); d.textContent = name; if (name === "Current layer only") { d.setAttribute("aria-checked", String(st.single)); d.setAttribute("role", "menuitemcheckbox"); }
    d.onclick = () => { mnu.style.display = "none"; applyPreset(name); }; mnu.appendChild(d); }
  const r = $("ls").getBoundingClientRect(); mnu.style.left = `${Math.max(8, r.right - 232)}px`; mnu.style.top = `${r.bottom + 6}px`;
  mnu.style.display = mnu.style.display === "block" ? "none" : "block"; };
window.addEventListener("click", () => { $("lsmenu").style.display = "none"; });
