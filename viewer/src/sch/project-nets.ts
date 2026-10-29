// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== project nets across sheets and the board (c0185)
import { draw } from "../board/draw";
import { docByFile, openDoc } from "../core/documents";
import { esc, showInfo } from "../core/dom";
import { PREVIEW_MODE } from "../core/env";
import { S, st } from "../core/state";
import { fit } from "../core/viewport";
import { buildNav } from "../panels/navigator";
import { isSch, SCH } from "./scene";
import { netBox, schSelect } from "./select";
import { imodel, irow, isection, netModel } from "../inspect/model";
import { inspect } from "../panels/inspector";
export let PROJ_NET = null;
export const BC = !PREVIEW_MODE && "BroadcastChannel" in window ? new BroadcastChannel("fenolite-view") : null;
export function shareNet(name) { PROJ_NET = name || null; if (BC) BC.postMessage({ net: PROJ_NET }); }
if (BC) BC.onmessage = e => { PROJ_NET = e.data && e.data.net || null; applyProjNet(); };
export function projectNetSection(n) {   // c0244: the project net of a sheet's net, for the inspector
  if (!n.project) return null;
  const others = (n.sheets || []).filter(x => !S.meta || x !== S.meta.name), pins = n.project_pins || [];
  return isection("Project net", [irow("Name", n.project), irow("Pins", pins.length), others.length ? irow("Also on", others.join(", "), { sheets: others }) : irow("Sheets", "this sheet only"),
    pins.length ? irow("Pin list", pins.slice(0, 60).join(", ") + (pins.length > 60 ? " …" : ""), { mono: false }) : null]);
}
export function schNetSection(n) { return isection("Net", [irow("Name", n.name || "(no name)"), irow("Pins", n.pins.length), n.pins.length ? irow("Pin list", n.pins.slice(0, 60).join(", ") + (n.pins.length > 60 ? " …" : "")) : null]); }
export function schNetModel(ni) { const n = S.nets[ni]; return imodel("net", n.name || "(no name)", [schNetSection(n), projectNetSection(n)], { subtitle: "Net", target: { sch: true, net: ni, comp: -1 } }); }
export function projectNetInfo(n) {
  if (!n.project) return "";
  const others = (n.sheets || []).filter(x => !S.meta || x !== S.meta.name);
  const links = others.map(x => `<a href="#" class="sheetlink" data-sheet="${esc(x)}">${esc(x)}</a>`).join(", ");
  return `<br><br><b>Project net ${esc(n.project)}</b>: ${(n.project_pins || []).length} pins` + (links ? `<br>Also on: ${links}` : "<br>On this sheet only") +
    `<br><small>${esc((n.project_pins || []).slice(0, 60).join(", "))}</small>`;
}
document.addEventListener("click", (e: any) => { const a = e.target.closest && e.target.closest(".sheetlink"); if (!a) return; e.preventDefault();
  const d = docByFile(a.dataset.sheet); if (d) openDoc(d); });
export function applyProjNet() {   // the shared net, selected on the sheet or board shown
  if (!PROJ_NET || !S) return;
  if (isSch()) { const i = S.nets.findIndex(n => (n.project || n.name) === PROJ_NET); if (i >= 0) selectNet(i, false, true); }
  else if (S.nets && !S.kind) { const i = S.nets.indexOf(PROJ_NET); if (i >= 0) { st.selNet = i; st.selComp = -1; inspect(() => netModel(i)); draw(); } }
}
export function selectNet(ni, zoom, quiet?) { SCH.sel = -1; SCH.selComp = -1; SCH.selNet = ni; const n = S.nets[ni];
  inspect(() => schNetModel(ni));
  if (!quiet) shareNet(n.project || n.name);
  const b = netBox(ni); if (zoom && b) fit([b[0] - 8, b[1] - 8, b[2] + 8, b[3] + 8]); else draw(); buildNav(); }
export function selectComp(ci, zoom) { const oi = S.objects.findIndex(o => o.k === "comp" && o.comp === ci); schSelect(oi);
  const b = S.comps[ci].b; if (zoom && b) fit([b[0] - 12, b[1] - 12, b[2] + 12, b[3] + 12]); }
