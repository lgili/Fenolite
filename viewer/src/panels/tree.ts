// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== project tree (left panel)
import { openDoc } from "../core/documents";
import { $, esc } from "../core/dom";
import { setSidebar } from "../core/input";
import { DOC, PROJECT } from "../core/state";
export const KIND_COLOR = { pcb: "#3fb950", schematic: "#d29922", "schematic-library": "#a371f7", "pcb-library": "#58a6ff", "integrated-library": "#58a6ff", "output-job": "#8b949e", rules: "#8b949e",
  stackup: "#8b949e", project: "#8b949e", "library-table": "#8b949e", draftsman: "#db61a2", other: "#6e7681" };
export function buildTree() {
  const box = $("tree"); box.innerHTML = "";
  if (!PROJECT) return;
  const head = document.createElement("div"); head.className = "proj"; head.textContent = PROJECT.project_file || PROJECT.name; head.title = `${PROJECT.source} project`; box.appendChild(head);
  for (const g of PROJECT.groups) {
    const gh = document.createElement("div"); gh.className = "grp"; gh.textContent = g.name; box.appendChild(gh);
    const list = document.createElement("div"); box.appendChild(list);
    gh.onclick = () => { gh.classList.toggle("closed"); list.style.display = gh.classList.contains("closed") ? "none" : "block"; };
    for (const d of g.documents) {
      const row = document.createElement("div"); row.className = "doc" + (DOC && DOC.id === d.id ? " sel" : "") + (d.present ? "" : " missing");
      row.title = `${d.path} · ${d.kind}${d.viewable ? "" : " (no viewer yet)"}`;
      row.innerHTML = `<span class="ic" style="background:${KIND_COLOR[d.kind] || KIND_COLOR.other}"></span>${esc(d.name)}`;
      row.onclick = () => { openDoc(d); setSidebar(false); }; list.appendChild(row);
    }
  }
}
