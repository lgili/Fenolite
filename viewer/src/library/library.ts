// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { loadBoard } from "../board/load";
import { toMM } from "../board/scene";
import { esc, showInfo } from "../core/dom";
import { st } from "../core/state";
import { fmtPair } from "../core/units";
import { loadSch } from "../sch/load";
import { toMMsch } from "../sch/scene";
import { $ } from "../core/dom";
// ================================================================== libraries (c0179): the item list, each item drawn as a board or a sheet
export let LIB = null, LIBSEL = -1, LIBQ = "";
export function setLib(v) { LIB = v; }
export function toUnits(sc) {
  if (sc.kind === "table") return sc;   // c0190: a BOM document or an output job
  if (sc.kind === "library") { for (const it of sc.items) if (it.scene) toUnits(it.scene); return sc; }
  return sc.kind === "schematic" ? toMMsch(sc) : toMM(sc);
}
export function itemNote(it) {
  if (it.copper_nm) { const b = it.copper_nm; return `${it.pads} pads · ${fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)}`; }
  return it.pins != null ? `${it.pins} pins` : "";
}
export function buildLibList() {
  const box = $("libList"); box.innerHTML = ""; if (!LIB) return; const q = LIBQ.trim().toLowerCase();
  $("libTitle").textContent = `${LIB.lib === "pcb" ? "Footprints" : LIB.lib === "drawing" ? "Sheets" : "Symbols"} (${LIB.items.length})`;
  LIB.items.forEach((it, i) => { if (q && !it.name.toLowerCase().includes(q) && !(it.description || "").toLowerCase().includes(q)) return;
    const d = document.createElement("div"); d.className = "navi" + (i === LIBSEL ? " sel" : ""); d.title = it.description || it.name;
    d.innerHTML = `${esc(it.name)} <small>${esc(itemNote(it))}</small>`; d.onclick = () => openItem(i); box.appendChild(d); });
}
export function itemInfo(it) {
  const rows = [...it.info];
  if (it.copper_nm) { const b = it.copper_nm; rows.push(["Copper extent", fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)]); }
  if (it.courtyard_nm) { const b = it.courtyard_nm; rows.push(["Courtyard", fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)]); }
  const title = `<b>Properties</b> · ${LIB.lib === "pcb" ? "Footprint" : LIB.lib === "drawing" ? "Sheet" : "Symbol"}`;
  const table = rows.length ? `<table>${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</table>` : "";
  return it.lib_id ? `<details><summary>${title} · ${esc(it.evidence || "INFERRED")}</summary>${table}</details>` : title + table;
}
export function openItem(i, keepView?) {
  LIBSEL = i; const it = LIB.items[i]; buildLibList();
  if (!it.scene) { showInfo(`<b>${esc(it.name)}</b> could not be drawn; see the notes.`); return; }
  if (it.scene.kind === "schematic") loadSch(it.scene, keepView); else loadBoard(it.scene, keepView);
  document.body.classList.add("lib"); $("fname").textContent = `${LIB.meta.name} › ${it.name}`;
  showInfo(itemInfo(it)); st.itemInfo = true;
}
export function loadLibrary(scene, keepView) {
  const prev = LIB && LIBSEL >= 0 ? LIB.items[LIBSEL].name : null; LIB = scene;
  document.body.classList.add("lib");
  let i = prev ? scene.items.findIndex(it => it.name === prev) : -1; if (i < 0) i = scene.items.findIndex(it => it.scene); if (i < 0) i = 0;
  if (!scene.items.length) { LIBSEL = -1; buildLibList(); showInfo("This library holds no item."); return; }
  openItem(i, keepView && prev !== null);
  if (scene.meta.notes && scene.meta.notes.length) $("notes").innerHTML += "<br>" + scene.meta.notes.map(esc).join("<br>");
}
$("libFilter").addEventListener("input", e => { LIBQ = e.target.value; buildLibList(); });
