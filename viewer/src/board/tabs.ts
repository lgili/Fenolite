// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== layer tabs (bottom bar)
import { $, esc } from "../core/dom";
import { S, st, vis } from "../core/state";
import { draw, VIEWL } from "./draw";
export const TAB_ORDER = id => { const k = id.endsWith(".Cu") ? (id === "F.Cu" ? 0 : id === "B.Cu" ? 2 : 1) : id.startsWith("Mech") ? 3 : id.endsWith("SilkS") ? 4 : id.endsWith("Paste") ? 5 : id.endsWith("Mask") ? 6
  : id.endsWith("CrtYd") ? 7 : id.endsWith("Fab") ? 8 : id === "Edge.Cuts" ? 9 : id.startsWith("View.") ? 11 : 10; return k; };
export function tabLayers() { return [...S.layers].sort((a, b) => (a.tab ?? TAB_ORDER(a.id) * 100) - (b.tab ?? TAB_ORDER(b.id) * 100) || (a.id.startsWith("B.") - b.id.startsWith("B.")) || a.id.localeCompare(b.id, undefined, { numeric: true })); }
export function buildTabs() {
  const box = $("tablist"); box.innerHTML = "";
  for (const l of tabLayers()) {
    const t = document.createElement("div"); t.className = "tab" + (l.id === st.cur ? " cur" : "") + (vis.get(l.id) ? "" : " off");
    t.style.borderBottomColor = l.id === st.cur ? l.color : "transparent"; t.title = `${l.name} (${l.kind}) · click: current layer · click the swatch or right-click: show / hide`;
    t.innerHTML = `<span class="sw" style="background:${l.color}"></span><span>${esc(l.name)}</span>`;
    (t.querySelector(".sw") as HTMLElement).onclick = e => { e.stopPropagation(); vis.set(l.id, !vis.get(l.id)); buildTabs(); draw(); };
    t.onclick = () => setCurrent(l.id);
    t.oncontextmenu = e => { e.preventDefault(); vis.set(l.id, !vis.get(l.id)); buildTabs(); draw(); };
    box.appendChild(t);
  }
  const cur = S.layers.find(l => l.id === st.cur); $("cur").textContent = cur ? `current: ${cur.name}${st.single ? " (single layer)" : ""}` : "";
}
export function setCurrent(id) { st.cur = id; vis.set(id, true); buildTabs(); draw(); }
export function stepCurrent(dir) { const L = tabLayers().filter(l => vis.get(l.id)); if (!L.length) return; let i = L.findIndex(l => l.id === st.cur); i = (i + dir + L.length) % L.length; setCurrent(L[i].id); }
export const SETS = { "All layers": () => true, "Signal layers": l => l.kind === "copper" || VIEWL(l.id), "Top side": l => l.side !== "bottom", "Bottom side": l => l.side !== "top", "Default": l => l.visible };
$("ls").onclick = e => { e.stopPropagation(); const mnu = $("lsmenu"); mnu.innerHTML = ""; for (const name of Object.keys(SETS)) { const d = document.createElement("div"); d.textContent = name;
  d.onclick = () => { for (const l of S.layers) vis.set(l.id, SETS[name](l)); mnu.style.display = "none"; buildTabs(); draw(); }; mnu.appendChild(d); } mnu.style.display = mnu.style.display === "block" ? "none" : "block"; };
window.addEventListener("click", () => { $("lsmenu").style.display = "none"; });
