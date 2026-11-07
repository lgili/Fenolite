// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the command palette (c0300, design decision 4)
// Ctrl+K (Cmd+K on macOS), or typing in the toolbar's search field: one field that runs a command of the registry
// or jumps to a part, a net, a document or a library item. Results come grouped by source, the best group first;
// arrows move, Enter runs or jumps (through the page's own selection functions and the navigation guard of
// openDoc), Esc closes and gives the focus back. ">" keeps commands, "@" parts, "#" nets.
import * as preact from "preact";
import { available, COMMANDS, keyLabel, runCommand } from "../core/commands";
import { allDocs, openDoc } from "../core/documents";
import { $, natural } from "../core/dom";
import { paletteMatch, paletteParse } from "../core/palette-match";
import { DOC, MM, S } from "../core/state";
import { fmtLen } from "../core/units";
import { LIB, openItem } from "../library/library";
import { selectCompAt, selectNetAt } from "../panels/review";
import { KIND_COLOR } from "../panels/tree";
import { selectComp, selectNet } from "../sch/project-nets";
import { isSch } from "../sch/scene";
import { Icon } from "../ui/icons";

const GROUPS = { command: "Commands", part: "Parts", net: "Nets", doc: "Documents", item: "Library" };
const KIND_ICON = { part: "chip", net: "net", doc: "doc", item: "chip" };
export const PAL = { query: "", active: 0, items: [], results: [], back: null as HTMLElement };
export function paletteItems() {   // every entry the palette can reach in what is shown now
  const out = [];
  for (const c of COMMANDS) if (available(c) && c.id !== "app.palette" && c.id !== "tools.escape")
    out.push({ kind: "command", label: c.title, alt: c.group, icon: c.icon, keys: c.keys.filter(k => k !== "=" && k !== "_").map(keyLabel), run: () => runCommand(c.id), disabled: c.disabled && c.disabled() });
  if (S && S.comps && S.kind !== "table") {
    const sch = isSch();
    const byRef = S.comps.map((c, i) => [c, i]).sort((a, b) => natural(a[0].ref, b[0].ref));
    for (const [c, i] of byRef) { if (c.hidden) continue;
      const sub = sch ? [c.comment, c.lib].filter(Boolean).join(" · ") : [c.value, c.footprint, c.side === "bottom" ? "bottom" : ""].filter(Boolean).join(" · ");
      out.push({ kind: "part", label: c.ref, alt: sch ? c.comment : c.value, sub, run: () => sch ? selectComp(i, true) : selectCompAt(i) }); }
    if (sch) S.nets.forEach((n, i) => { if (n.name) out.push({ kind: "net", label: n.name, sub: `${n.pins.length} pins`, run: () => selectNet(i, true) }); });
    else S.nets.forEach((n, i) => { if (!n) return; const info = (S.netinfo || [])[i];
      out.push({ kind: "net", label: n, sub: info ? `${info.pads} pads · ${fmtLen(info.length * MM)}` : "", run: () => selectNetAt(i) }); });
  }
  if (LIB) LIB.items.forEach((it, i) => out.push({ kind: "item", label: it.name, sub: it.description || "", run: () => openItem(i) }));
  for (const d of allDocs()) if (d.viewable && d.present)
    out.push({ kind: "doc", label: d.name, sub: d.path, color: KIND_COLOR[d.kind] || KIND_COLOR.other, current: DOC && DOC.id === d.id, run: () => openDoc(d) });
  return out;
}
function grouped(results) {   // the results by source, the group of the best result first, each in rank order
  const order = [], by = new Map();
  for (const r of results) { if (!by.has(r.kind)) { by.set(r.kind, []); order.push(r.kind); } by.get(r.kind).push(r); }
  return order.map(k => [k, by.get(k)]);
}
function refine() {
  const { q, kind } = paletteParse(PAL.query);
  let pool = PAL.items;
  if (!q && !kind) pool = pool.filter(it => it.kind === "command" || it.kind === "doc");   // nothing typed: what to do, where to go
  PAL.results = grouped(paletteMatch(PAL.query, pool)).flatMap(g => g[1]);
  PAL.active = Math.min(PAL.active, Math.max(PAL.results.length - 1, 0));
}
export function Palette() {
  const groups = grouped(PAL.results), { kind } = paletteParse(PAL.query);
  let n = -1;
  return <div class="palBox">
    <div class="palField">
      <Icon name="search" />
      <input id="palInput" role="combobox" aria-expanded="true" aria-controls="palList" aria-autocomplete="list"
        aria-activedescendant={PAL.results.length ? `pal${PAL.active}` : undefined} placeholder="Search parts, nets and documents, or run a command…"
        value={PAL.query} autocomplete="off" spellcheck={false} onInput={e => { PAL.query = (e.target as HTMLInputElement).value; PAL.active = 0; refine(); renderPalette(); }}
        onKeyDown={paletteKey} />
      <kbd>Esc</kbd>
    </div>
    <div id="palList" role="listbox" aria-label="Results">
      {PAL.results.length ? groups.map(([k, list]) => <div role="group" aria-label={GROUPS[k]} key={k}>
        <div class="palGroup">{GROUPS[k]}</div>
        {list.map(r => { n++; const i = n;
          return <div id={`pal${i}`} key={i} role="option" aria-selected={Boolean(i === PAL.active)} aria-disabled={r.disabled ? true : undefined}
            class={"palItem" + (i === PAL.active ? " active" : "")} onMouseMove={() => { if (PAL.active !== i) { PAL.active = i; renderPalette(); } }}
            onClick={() => choose(i)}>
            <span class="palIc">{r.color ? <span class="dot" style={`background:${r.color}`}></span> : <Icon name={r.icon || KIND_ICON[r.kind]} />}</span>
            <span class="palText"><span class="palLabel">{r.label}</span>{r.sub ? <small>{r.sub}</small> : null}</span>
            {r.current ? <span class="palTag">Open</span> : null}
            {(r.keys || []).map(k => <kbd>{k}</kbd>)}
          </div>; })}
      </div>) : <div class="palEmpty">{PAL.query.trim() ? `Nothing matches “${PAL.query.trim()}”` + (kind ? ` among ${GROUPS[kind].toLowerCase()}.` : ".") : "Type to search."}</div>}
    </div>
    <div class="palFoot"><span><kbd>↑</kbd><kbd>↓</kbd> move</span><span><kbd>Enter</kbd> open or run</span>
      <span><kbd>&gt;</kbd> commands</span><span><kbd>@</kbd> parts</span><span><kbd>#</kbd> nets</span></div>
  </div>;
}
function paletteKey(e: KeyboardEvent) {
  const n = PAL.results.length;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); if (!n) return; PAL.active = (PAL.active + (e.key === "ArrowDown" ? 1 : -1) + n) % n; renderPalette(); scrollActive(); }
  else if (e.key === "Enter" && !e.isComposing) { e.preventDefault(); choose(PAL.active); }
  else if ((e.key === "k" || e.key === "K") && (e.ctrlKey || e.metaKey)) { e.preventDefault(); closePalette(true); }
}
function scrollActive() { document.getElementById(`pal${PAL.active}`)?.scrollIntoView({ block: "nearest" }); }
function choose(i) {
  const r = PAL.results[i]; if (!r || r.disabled) return;
  closePalette(false); (document.activeElement as HTMLElement)?.blur?.(); r.run();
}
export function renderPalette() { preact.render(<Palette />, $("palette")); }
export function openPalette(query = "") {
  const dlg = $("palette");
  if (dlg.open) { PAL.query = query || PAL.query; refine(); renderPalette(); $("palInput").focus(); return; }
  PAL.back = document.activeElement as HTMLElement; PAL.query = query; PAL.active = 0; PAL.items = paletteItems(); refine();
  renderPalette(); dlg.showModal();
  const input = $("palInput"); input.focus(); input.setSelectionRange(input.value.length, input.value.length);
}
export function closePalette(restore = true) {
  const dlg = $("palette"); if (dlg.open) dlg.close();
  if (restore && PAL.back && PAL.back.isConnected && PAL.back !== document.body) PAL.back.focus?.();
  PAL.items = []; PAL.results = [];
}
$("palette").addEventListener("cancel", e => { e.preventDefault(); closePalette(true); });
$("palette").addEventListener("click", e => { if (e.target === $("palette")) closePalette(true); });   // the backdrop
