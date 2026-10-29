// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== scene, overlays and notes
// findings by group (change c0193): the box draws or hides a group, the title opens its items, the tooltip says the rule;
// a Preact component (change c0247)
import * as preact from "preact";
import { draw } from "../board/draw";
import { ovGroup } from "../board/overlays";
import { $, esc, showInfo } from "../core/dom";
import { flip } from "../core/input";
import { S, st, view } from "../core/state";
import { fit } from "../core/viewport";
import { set3D } from "../three/view3d";
import { Icon } from "../ui/icons";
import { showSection } from "../ui/section";
import { Empty } from "../ui/states";
function showGroup(id, on) { if (on) st.ovOff.delete(id); else st.ovOff.add(id); draw(); }
function openGroup(id) { if (st.ovOpen.has(id)) st.ovOpen.delete(id); else st.ovOpen.add(id); buildFindings(); }
// keys: a row is never reused for a row of another kind, so no attribute of one is left on the other
function GroupRow({ g, idx }: { g: any, idx: number[] }) {
  return <div class={"fg" + (idx.length ? "" : " zero")} title={g.note || ""}>
    <input type="checkbox" checked={!st.ovOff.has(g.id)} aria-label={`Draw ${g.title}`} onChange={e => showGroup(g.id, (e.target as HTMLInputElement).checked)} />
    <span class="sw" style={`background:${g.color}`}></span>
    <span class="ft" role="button" tabIndex={0} aria-expanded={Boolean(st.ovOpen.has(g.id))} onClick={() => openGroup(g.id)}
      onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openGroup(g.id); } }}>{g.title}</span>
    <span class="fn">{idx.length}</span>
  </div>;
}
export function FindingsPanel({ groups, byG }: { groups: any[], byG: Map<string, number[]> }) {
  const out = [], zero = groups.filter(g => !(byG.get(g.id) || []).length);
  const rows = (g, idx) => {
    out.push(<GroupRow key={"g:" + g.id} g={g} idx={idx} />);
    if (!st.ovOpen.has(g.id)) return;
    if (g.note) out.push(<div key={"n:" + g.id} class="fnote">{g.note}</div>);
    for (const i of idx) out.push(<div key={"o:" + i} class={"ov" + (i === st.selOv ? " sel" : "")} onClick={() => gotoFinding(i)}>{S.overlays[i].label}</div>);
  };
  for (const g of groups) { const idx = byG.get(g.id) || []; if (idx.length) rows(g, idx); }
  if (zero.length) {   // c0243: the groups with no finding fold into one line; each stays a result, one click away
    out.push(<button key="zero" id="ovZero" type="button" class="zeroLine" aria-expanded={Boolean(!!st.ovZeroOpen)} onClick={() => { st.ovZeroOpen = !st.ovZeroOpen; buildFindings(); }}>
      <span class="chev"><Icon name="chevRight" size={12} /></span>{`${zero.length} group${zero.length === 1 ? "" : "s"} with no findings`}</button>);
    if (st.ovZeroOpen) for (const g of zero) rows(g, []);
  }
  if (!groups.length) out.push(<Empty key="empty" text="No finding groups for this board." />);
  return <>{out}</>;
}
export function buildFindings() {
  const groups = [...(S.meta.findings || [])], byG = new Map();
  (S.overlays || []).forEach((o, i) => { const g = ovGroup(o); if (!byG.has(g)) byG.set(g, []); byG.get(g).push(i); });
  for (const g of byG.keys()) if (!groups.some(x => x.id === g)) groups.push({ id: g, title: g, color: S.overlays[byG.get(g)[0]].color, n: byG.get(g).length, note: "" });
  const total = (S.overlays || []).length;
  showSection("findings", groups.length > 0, total, "Findings", total ? "warn" : "");
  preact.render(<FindingsPanel groups={groups} byG={byG} />, $("overlays"));
}
export function clearFindings() { showSection("findings", false); preact.render(null, $("overlays")); }   // a sheet: no finding group
export function gotoFinding(i) {
  const o = S.overlays[i]; if (st.mode3d) set3D(false); st.selOv = i; st.selNet = -1; st.selComp = -1; st.ovOff.delete(ovGroup(o));
  const xs = o.pts.map(p => p[0]), ys = o.pts.map(p => p[1]);
  const b = o.bbox ? [Math.min(o.bbox[0], ...xs), Math.min(o.bbox[1], ...ys), Math.max(o.bbox[2], ...xs), Math.max(o.bbox[3], ...ys)] : [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
  if (o.layer && (o.layer.startsWith("B.") !== view.mirror)) flip();
  const g = (S.meta.findings || []).find(x => x.id === ovGroup(o));
  fit([b[0] - 4, b[1] - 4, b[2] + 4, b[3] + 4]); buildFindings();
  showInfo(`<b>${esc(g ? g.title : ovGroup(o))}</b><br>${esc(o.label)}${g && g.note ? `<br><small>${esc(g.note)}</small>` : ""}`);
}
