// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The Navigator of a sheet (c0177), a Preact component (change c0247): its parts and its nets, filtered; a click
// selects and frames one.
import * as preact from "preact";
import { $, natural } from "../core/dom";
import { S } from "../core/state";
import { selectComp, selectNet } from "../sch/project-nets";
import { isSch, SCH } from "../sch/scene";

// keys: a part row is never reused for a net row (no title left behind)
export function NavigatorPanel({ comps, nets }: { comps: any[], nets: any[] }) {
  return <>
    <div key="hc" class="navg">{`Components (${comps.length})`}</div>
    {comps.map(([c, i]) => <div key={"c:" + i} class={"navi" + (SCH.selComp === i ? " sel" : "")} title={c.description || c.lib || ""} onClick={() => selectComp(i, true)}>
      {`${c.ref} `}<small>{String(c.comment || c.lib || "")}</small>
    </div>)}
    <div key="hn" class="navg">{`Nets (${nets.length})`}</div>
    {nets.map(([n, i]) => <div key={"n:" + i} class={"navi" + (SCH.selNet === i ? " sel" : "")} onClick={() => selectNet(i, true)}>
      {String(n.name)}{n.project && n.project !== n.name ? " " : null}{n.project && n.project !== n.name ? <small>{`→ ${n.project}`}</small> : null}
      {" "}<small>{`${n.pins.length}${n.sheets && n.sheets.length > 1 ? ` · ${n.sheets.length} sheets` : ""}`}</small>
    </div>)}
  </>;
}
export function buildNav() {
  const box = $("navList"); if (!box || !isSch()) return; const q = SCH.filter.trim().toLowerCase();
  const comps = S.comps.map((c, i) => [c, i]).filter(([c]) => !c.hidden).filter(([c]) => !q || c.ref.toLowerCase().includes(q) || (c.comment || "").toLowerCase().includes(q)).sort((a, b) => natural(a[0].ref, b[0].ref));
  const nets = S.nets.map((n, i) => [n, i]).filter(([n]) => n.name && (n.pins.length > 1 || !n.name.startsWith("Net")) && (!q || n.name.toLowerCase().includes(q))).sort((a, b) => natural(a[0].name, b[0].name));
  preact.render(<NavigatorPanel comps={comps} nets={nets} />, box);
}
$("navFilter").addEventListener("input", e => { SCH.filter = e.target.value; buildNav(); });
