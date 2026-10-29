// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { draw } from "../board/draw";
import { buildVariants } from "../board/variants";
import { allDocs, docByFile, navigation, openDoc, sceneOf } from "../core/documents";
import { esc, natural, showInfo } from "../core/dom";
import { find } from "../core/input";
import { DOC, S, cv, st, view } from "../core/state";
import { fit, fitted } from "../core/viewport";
import { buildDiffList } from "../panels/changes";
import { buildMessages } from "../panels/messages";
import { buildNav } from "../panels/navigator";
import { KIND_COLOR } from "../panels/tree";
import { schPick } from "./hit";
import { applyProjNet, selectComp, selectNet } from "./project-nets";
import { SCH, toMMsch } from "./scene";
import { set3D } from "../three/view3d";
import { $ } from "../core/dom";
import { setS } from "../core/state";
import { setFitted } from "../core/viewport";
export function sheetTabs() {   // the bottom bar of a schematic: the project's viewable documents, as the native tool's document tabs
  const box = $("tablist"); box.innerHTML = "";
  const docs = allDocs().filter(d => d.viewable && d.present).sort((a, b) => ((a.kind !== "schematic") as any) - ((b.kind !== "schematic") as any) || natural(a.name, b.name));
  for (const d of docs) { const t = document.createElement("div"); t.className = "tab doc-tab" + (DOC && DOC.id === d.id ? " cur" : "");
    t.style.borderBottomColor = DOC && DOC.id === d.id ? (KIND_COLOR[d.kind] || "#888") : "transparent";
    t.innerHTML = `<span class="sw" style="background:${KIND_COLOR[d.kind] || "#888"}"></span><span>${esc(d.name)}</span>`; t.title = d.path; t.onclick = () => openDoc(d); box.appendChild(t); }
  $("cur").textContent = S ? `${S.sheet.style} sheet · ${S.comps.length} parts · ${S.nets.filter(n => n.name).length} nets` : "";
}

export async function crossProbe(ref, kind) {   // open the first document of `kind` that holds the part `ref`, and select it there
  const want = ref.toLowerCase(), generation = navigation;
  for (const d of allDocs().filter(x => x.kind === kind && x.viewable && x.present)) {
    let sc = null; try { sc = await sceneOf(d); } catch (e) { if (generation !== navigation) return false; continue; }
    if (generation !== navigation) return false; if (!sc) continue;
    const ok = sc.comps.some(c => c.ref.toLowerCase() === want || (c.group || "").toLowerCase() === want);
    if (ok) { const shown = await openDoc(d); if (!shown || shown !== navigation) return false; find(ref); return true; } }
  showInfo(`No ${kind === "pcb" ? "board" : "schematic"} of this project holds <b>${esc(ref)}</b>.`); return false;
}
export function schDouble(X, Y) {
  const oi = schPick(X, Y); if (oi < 0) return; const o = S.objects[oi];
  if (o.k === "sheet" && o.file) { const d = docByFile(o.file); if (d) openDoc(d); else showInfo(`The sheet <b>${esc(o.file)}</b> is not a viewable document of this project.`); return; }
  const ci = o.comp; if (ci >= 0) { const c = S.comps[ci]; crossProbe(c.group || c.ref, "pcb"); }
}
export function schFind(q) {
  const ql = q.toLowerCase(); let ci = S.comps.findIndex(c => c.ref.toLowerCase() === ql);
  if (ci < 0) ci = S.comps.findIndex(c => (c.group || "").toLowerCase() === ql);
  if (ci >= 0) { selectComp(ci, true); return; }
  const ni = S.nets.findIndex(n => n.name && n.name.toLowerCase() === ql);
  if (ni >= 0) { selectNet(ni, true); return; }
  showInfo(`Nothing named <b>${esc(q)}</b> on this sheet.`);
}
export function loadSch(scene, keepView) {
  st.itemInfo = false;
  const first = S === null || S !== scene && !keepView; if (!scene.mm) toMMsch(scene); setS(scene);
  document.body.classList.add("sch"); if (st.mode3d) set3D(false);
  SCH.sel = -1; SCH.selNet = -1; SCH.selComp = -1; showInfo(null);
  cv.style.display = "block"; view.mirror = false;
  $("fname").textContent = S.meta.name; document.title = S.meta.name + " · Fenolite viewer";
  $("gen").textContent = S.meta.sha256 ? `SHA-256 ${S.meta.sha256.slice(0, 12)}` : "";
  const c = S.meta.counts || {};
  $("ovTitle").style.display = "none"; $("overlays").innerHTML = "";
  $("notes").innerHTML = (S.meta.notes || []).map(esc).join("<br>") + `<br>Read by the ${esc(S.meta.backend)} backend, evidence ${esc(S.meta.evidence)}.` +
    (c.kinds ? `<br>${c.items || 0} items: ${Object.entries(c.kinds).map(([k, n]) => `${n} ${esc(k)}`).join(" · ")}`   // a Draftsman sheet (c0180)
      : `<br>${c.components || 0} parts · ${c.pins || 0} pins · ${c.wires || 0} wires · ${c.nets || 0} nets · ${c.power_ports || 0} power ports · ${c.ports || 0} ports`);
  sheetTabs(); buildNav(); buildDiffList(); buildMessages(); buildVariants(); applyProjNet();
  if (first) { setFitted(false); fit(); } else draw();
}
