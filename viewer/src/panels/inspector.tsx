// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the inspector (c0269, design decisions 2 and 3)
// renderInspector(model) draws an inspector model of inspect/model in the dock's Properties tab (#info): a title,
// the actions that apply to the selection (registry commands, c0268), then one section per kind of value, each
// row with its copy control, and "Copy all". With nothing selected #info is empty and the document's summary
// (#infoEmpty) shows instead. A legacy HTML message still renders through showInfo(html).
import * as preact from "preact";
import { available, COMMANDS, keyLabel, runCommand } from "../core/commands";
import { $ } from "../core/dom";
import { DOC, S, st } from "../core/state";
import { UNIT } from "../core/units";
import { modelText } from "../inspect/model";
import { LIB } from "../library/library";
import { isSch } from "../sch/scene";
import { Icon } from "../ui/icons";
import { copyAndSay } from "../ui/toast";
import { dockShowSelection } from "./dock";
import { waiveState } from "../core/commands";
import { RUNS, runAgainAction } from "../review/runs";

export const INSPECT = { model: null as any, waive: false };
const KIND_LABEL = { pad: "Pad", track: "Track", arc: "Arc", via: "Via", hole: "Hole", zone: "Zone", keepout: "Keep-out", part: "Part", net: "Net",
  finding: "Finding", item: "Item", body: "3D body", symbol: "Symbol", footprint: "Footprint", sheet: "Sheet", component: "Component", wire: "Wire",
  mark: "Review mark", measure: "Measurement", note: "" };
function Row({ r }: { r: any }) {
  const value = r.link ? <a href={r.link} target="_blank" rel="noopener noreferrer">{r.value}</a>
    : r.sheets ? <>{r.sheets.map((x, i) => <>{i ? ", " : ""}<a href="#" class="sheetlink" data-sheet={x}>{x}</a></>)}</> : r.value;
  return <div class="irow">
    <span class="ik">{r.label}</span>
    <span class={"iv" + (r.mono ? " mono" : "")}>{value}{r.note ? <small>{r.note}</small> : null}</span>
    {r.copy ? <button type="button" class="tb icon small ghost icopy" aria-label={`Copy ${r.label}`} data-tip={`Copy ${r.label.toLowerCase()}`}
      onClick={() => copyAndSay(r.value, `${r.label} copied`)}><Icon name="copy" size={14} /></button> : null}
  </div>;
}
function WaiveForm() {   // c0271: the reason of a waiver, then the plan of the action
  const i = INSPECT.model.target.finding;
  const go = () => { const f = $("inspReason") as HTMLInputElement, reason = f.value.trim(); if (!reason) { f.focus(); return; } window.FenoliteActions.plan("waive", { finding: i, reason }); };
  return <div class="waiveForm">
    <label for="inspReason">Reason for the waiver <small>stored in the project file</small></label>
    <input id="inspReason" maxLength={300} placeholder="Accepted by design: …" onKeyDown={e => { if (e.key === "Enter") go(); }} />
    <div class="row"><button type="button" class="tb small accentBtn" id="inspWaivePlan" onClick={go}><Icon name="waive" size={14} /><span class="lbl">Review plan…</span></button>
      <button type="button" class="tb small" onClick={() => { INSPECT.waive = false; refreshInspector(); }}>Cancel</button></div>
  </div>;
}
function StaleNote({ why }: { why: string }) {   // c0271 fix: why Waive is not offered, and Run again
  const again = DOC ? runAgainAction(DOC.id) : null;
  return <div class="staleNote" id="inspWaiveWhy" role="status"><Icon name="alert" size={14} /><p>{`Waive is not offered. ${why}`}</p>
    {again ? <button type="button" id="inspRunAgain" class="tb small" disabled={!!RUNS.job} onClick={again.run}><Icon name="refresh" size={14} /><span class="lbl">{again.label}</span></button> : null}</div>;
}
export function InspectorActions() {
  const acts = COMMANDS.filter(c => c.group === "Selection" && available(c)), waive = waiveState();
  if (!acts.length && !waive.why) return null;
  return <><div class="inspActs" role="toolbar" aria-label="Actions on the selection">
    {acts.map(c => <button type="button" id={c.domId} class={"tb small act" + (c.tone ? " " + c.tone : "")} disabled={c.disabled && c.disabled()}
      data-tip={c.tip ? c.tip() : c.title} data-keys={c.keys.map(keyLabel).join(",") || undefined} onClick={() => runCommand(c.id)}>
      <Icon name={c.icon} size={14} /><span class="lbl">{c.label ? c.label() : c.title}</span></button>)}
  </div>
  {INSPECT.waive && waive.offered ? <WaiveForm /> : null}
  {waive.why ? <StaleNote why={waive.why} /> : null}</>;
}
export function Inspector({ model }: { model: any }) {
  if (model.html) return <div class="insp"><div class="ihtml" dangerouslySetInnerHTML={{ __html: model.html }} /></div>;
  return <div class="insp" data-kind={model.kind}>
    <header class="inspHead">
      <div class="inspTitle">
        {KIND_LABEL[model.kind] ? <span class="inspKind">{KIND_LABEL[model.kind]}</span> : null}
        <h2 id="inspTitle">{model.title}</h2>
        {model.subtitle ? <p>{model.subtitle}</p> : null}
      </div>
      {model.sections.length ? <button type="button" id="inspCopyAll" class="tb small ghost" data-tip="Copy every row as text"
        onClick={() => copyAndSay(modelText(model), "Properties copied")}><Icon name="copy" size={14} /><span class="lbl">Copy all</span></button> : null}
    </header>
    {model.note ? <p class="inspNote">{model.note}</p> : null}
    <InspectorActions />
    {model.extra ? model.extra() : null}
    {model.sections.map((s, k) => <details key={s.title + k} class="isect" open={!s.collapsed}>
      <summary><span class="chev"><Icon name="chevRight" size={12} /></span>{s.title}</summary>
      <div class="irows">{s.rows.map(r => <Row r={r} />)}</div>
    </details>)}
  </div>;
}
export function renderInspector(model) {
  INSPECT.model = model || null;
  preact.render(model ? <Inspector key={`${model.kind}:${model.title}`} model={model} /> : null, $("info"));
}
export function showModel(model) { INSPECT.waive = false; renderInspector(model); if (model) dockShowSelection(); }
export function inspectQuiet(build) { const m = build(); if (m) m.rebuild = build; INSPECT.waive = false; renderInspector(m); }
export function inspect(build) { const m = build(); if (m) m.rebuild = build; showModel(m); }   // a model built again when the unit changes
export function refreshInspector() {   // the unit changed, or what the actions offer
  const m = INSPECT.model; if (!m) return; if (m.rebuild) { const again = m.rebuild(); again.rebuild = m.rebuild; renderInspector(again); } else renderInspector(m);
}
// ---- the document's summary, shown while nothing is selected
export function DocSummary() {
  if (!S || !DOC) return <div class="docSum"><p class="hint">No document is open.</p></div>;
  const m = S.meta || {}, c = m.counts || {}, rows = [];
  const add = (k, v) => { if (v !== undefined && v !== null && v !== "") rows.push([k, String(v)]); };
  if (S.kind === "table") { add("Rows", S.rows.length); add("Columns", S.columns.length); }
  else if (LIB) { add("Items", LIB.items.length); add("Library", LIB.lib === "pcb" ? "footprints" : LIB.lib === "drawing" ? "sheets" : "symbols"); }
  else if (isSch()) { add("Parts", c.components); add("Nets", c.nets); add("Wires", c.wires); add("Pins", c.pins); add("Sheet", S.sheet && S.sheet.style); }
  else { add("Parts", c.footprints); add("Pads", c.pads); add("Tracks", c.tracks); add("Vias", c.vias); add("Zones", c.zones); add("Layers", (S.layers || []).filter(l => l.kind !== "view").length); }
  add("Evidence", m.evidence); add("Notes", (m.notes || []).length || null);
  return <div class="docSum">
    <div class="inspHead"><div class="inspTitle"><span class="inspKind">Document</span><h2>{DOC.name}</h2><p>{`${DOC.kind} · read by the ${m.backend || "?"} backend`}</p></div></div>
    <dl class="sumGrid">{rows.map(([k, v]) => <div><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
    <p class="hint"><Icon name="info" size={14} />{S.kind === "table" ? "Click a row that names a document or parts to open it." : `Click ${isSch() ? "a part, a pin or a wire" : "a pad, a track, a via or a zone"} to see its properties here. Lengths read in ${UNIT === "mm" ? "millimetres" : "mil"} (Q).`}</p>
  </div>;
}
export function refreshSummary() { preact.render(<DocSummary />, $("infoEmpty")); }
