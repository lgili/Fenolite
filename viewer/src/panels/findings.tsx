// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { draw } from "../board/draw";
import { ovGroup } from "../board/overlays";
import { esc, showInfo } from "../core/dom";
import { flip } from "../core/input";
import { S, st, view } from "../core/state";
import { fit } from "../core/viewport";
import { set3D } from "../three/view3d";
import { $ } from "../core/dom";
// ================================================================== scene, overlays and notes
// findings by group (change c0193): the box draws or hides a group, the title opens its items, the tooltip says the rule
export function buildFindings() {
  const box = $("overlays"); box.innerHTML = "";
  const groups = [...(S.meta.findings || [])], byG = new Map();
  (S.overlays || []).forEach((o, i) => { const g = ovGroup(o); if (!byG.has(g)) byG.set(g, []); byG.get(g).push(i); });
  for (const g of byG.keys()) if (!groups.some(x => x.id === g)) groups.push({ id: g, title: g, color: S.overlays[byG.get(g)[0]].color, n: byG.get(g).length, note: "" });
  $("ovTitle").style.display = groups.length ? "block" : "none";
  for (const g of groups) {
    const idx = byG.get(g.id) || [], row = document.createElement("div"); row.className = "fg" + (idx.length ? "" : " zero"); row.title = g.note || "";
    row.innerHTML = `<input type="checkbox" ${st.ovOff.has(g.id) ? "" : "checked"}><span class="sw" style="background:${esc(g.color)}"></span><span class="ft">${st.ovOpen.has(g.id) ? "\u25BE" : "\u25B8"} ${esc(g.title)}</span><span class="fn">${idx.length}</span>`;
    row.querySelector("input").onchange = e => { if ((e.target as HTMLInputElement).checked) st.ovOff.delete(g.id); else st.ovOff.add(g.id); draw(); };
    (row.querySelector(".ft") as HTMLElement).onclick = () => { if (st.ovOpen.has(g.id)) st.ovOpen.delete(g.id); else st.ovOpen.add(g.id); buildFindings(); };
    box.appendChild(row);
    if (!st.ovOpen.has(g.id)) continue;
    if (g.note) { const n = document.createElement("div"); n.className = "fnote"; n.textContent = g.note; box.appendChild(n); }
    for (const i of idx) { const d = document.createElement("div"); d.className = "ov" + (i === st.selOv ? " sel" : ""); d.textContent = S.overlays[i].label; d.onclick = () => gotoFinding(i); box.appendChild(d); }
  }
}
export function gotoFinding(i) {
  const o = S.overlays[i]; if (st.mode3d) set3D(false); st.selOv = i; st.selNet = -1; st.selComp = -1; st.ovOff.delete(ovGroup(o));
  const xs = o.pts.map(p => p[0]), ys = o.pts.map(p => p[1]);
  const b = o.bbox ? [Math.min(o.bbox[0], ...xs), Math.min(o.bbox[1], ...ys), Math.max(o.bbox[2], ...xs), Math.max(o.bbox[3], ...ys)] : [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  if (o.layer && (o.layer.startsWith("B.") !== view.mirror)) flip();
  const g = (S.meta.findings || []).find(x => x.id === ovGroup(o));
  fit([b[0] - 4, b[1] - 4, b[2] + 4, b[3] + 4]); buildFindings();
  showInfo(`<b>${esc(g ? g.title : ovGroup(o))}</b><br>${esc(o.label)}${g && g.note ? `<br><small>${esc(g.note)}</small>` : ""}`);
}
