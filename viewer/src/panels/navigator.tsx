// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { esc, natural } from "../core/dom";
import { S } from "../core/state";
import { selectComp, selectNet } from "../sch/project-nets";
import { SCH, isSch } from "../sch/scene";
import { $ } from "../core/dom";
export function buildNav() {
  const box = $("navList"); if (!box || !isSch()) return; const q = SCH.filter.trim().toLowerCase(); box.innerHTML = "";
  const comps = S.comps.map((c, i) => [c, i]).filter(([c]) => !c.hidden).filter(([c]) => !q || c.ref.toLowerCase().includes(q) || (c.comment || "").toLowerCase().includes(q)).sort((a, b) => natural(a[0].ref, b[0].ref));
  const nets = S.nets.map((n, i) => [n, i]).filter(([n]) => n.name && (n.pins.length > 1 || !n.name.startsWith("Net")) && (!q || n.name.toLowerCase().includes(q))).sort((a, b) => natural(a[0].name, b[0].name));
  const head = t => { const d = document.createElement("div"); d.className = "navg"; d.textContent = t; box.appendChild(d); };
  head(`Components (${comps.length})`);
  for (const [c, i] of comps) { const d = document.createElement("div"); d.className = "navi" + (SCH.selComp === i ? " sel" : ""); d.innerHTML = `${esc(c.ref)} <small>${esc(c.comment || c.lib || "")}</small>`; d.title = c.description || c.lib || ""; d.onclick = () => selectComp(i, true); box.appendChild(d); }
  head(`Nets (${nets.length})`);
  for (const [n, i] of nets) { const d = document.createElement("div"); d.className = "navi" + (SCH.selNet === i ? " sel" : ""); d.innerHTML = `${esc(n.name)}${n.project && n.project !== n.name ? ` <small>→ ${esc(n.project)}</small>` : ""} <small>${n.pins.length}${n.sheets && n.sheets.length > 1 ? ` · ${n.sheets.length} sheets` : ""}</small>`; d.onclick = () => selectNet(i, true); box.appendChild(d); }
}
$("navFilter").addEventListener("input", e => { SCH.filter = e.target.value; buildNav(); });
