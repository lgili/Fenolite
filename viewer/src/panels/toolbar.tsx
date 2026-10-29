// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the toolbar (c0268, design decision 3)
// Built from the command registry: the document title with "About this document", then three groups, View
// (2D/3D, Fit, Top/Bottom with the far side's opacity), Tools (Measure with its Point and Edge gap modes, Mark,
// units) and Share (Copy link, Export: SVG and Print at a scale). At the right: Run checks when the server runs
// them, the variant selector, the search field that opens the palette, the theme and the shortcut sheet. A
// control that does not apply to what is shown is not rendered. At 760 px and below the groups show icons only
// and Share moves into the overflow menu.
import * as preact from "preact";
import { setVariant, VARIANT, variantNames } from "../board/variants";
import { available, commandById, COMMANDS, keyLabel, runCommand } from "../core/commands";
import { $ } from "../core/dom";
import { find } from "../core/input";
import { DOC, S, st, view } from "../core/state";
import { THEME } from "../core/theme";
import { UNIT } from "../core/units";
import { draw } from "../board/draw";
import { openPalette } from "../dialogs/palette";
import { RUNS } from "../review/runs";
import { Icon } from "../ui/icons";
import { Menu, MenuItem } from "../ui/menu";
import { DOCK, dockNarrow } from "./dock";

export let DOC_TITLE = "Fenolite viewer";
export function setDocTitle(name, base?) { DOC_TITLE = name; document.title = (base || name) + " · Fenolite viewer"; refreshToolbar(); }
const keysOf = id => (commandById(id)?.keys || []).filter(k => k !== "=" && k !== "_").map(keyLabel).join(",");
const can = id => { const c = commandById(id); return !!c && available(c); };
const tipOf = id => commandById(id)?.title || id;

function Btn({ id, cmd, icon, text, tip, keys, pressed, onClick, disabled, cls }:
  { id: string, cmd?: string, icon: string, text?: string, tip?: string, keys?: string, pressed?: boolean, onClick?: () => void, disabled?: boolean, cls?: string }) {
  const label = tip || (cmd ? tipOf(cmd) : text);
  return <button id={id} type="button" class={"tb" + (text ? "" : " icon") + (cls ? " " + cls : "")} aria-label={label}
    aria-keyshortcuts={(keys ?? (cmd ? keysOf(cmd) : "")).split(",").filter(Boolean).map(k => k.replace(/ /g, "+")).join(" ") || undefined}
    aria-pressed={pressed} data-tip={label} data-keys={keys ?? (cmd ? keysOf(cmd) : undefined)}
    disabled={disabled} onClick={onClick || (() => runCommand(cmd))}>
    <Icon name={icon} />{text ? <span class="lbl">{text}</span> : null}
  </button>;
}
function printItems(): MenuItem[] {
  return COMMANDS.filter(c => c.id.startsWith("share.print.")).map(c => ({ id: "bPrint" + c.id.slice(12).replace("fit", "Fit"), title: c.title.replace("Print · ", ""), icon: "printer", run: () => runCommand(c.id), disabled: !available(c) }));
}
function exportItems(): MenuItem[] {
  return [{ id: "bSvg", title: "Save as SVG", icon: "image", run: () => runCommand("share.svg"), disabled: !can("share.svg") }, { sep: true }, { heading: "Print, or save as PDF" }, ...printItems()];
}
function OpacityPanel() {
  return <div class="menuForm">
    <label for="opac">Other side opacity <output>{Math.round(st.opac * 100)} %</output></label>
    <input id="opac" type="range" min="0" max="100" value={Math.round(st.opac * 100)}
      onInput={e => { st.opac = +(e.target as HTMLInputElement).value / 100; draw(); refreshToolbar(); }} />
    <p>The layers of the side you look away from, drawn under the near side.</p>
  </div>;
}
export function Toolbar() {
  const boardKind = can("view.3d"), flat = can("tools.measure"), runs = can("app.run");
  const measuring = st.measure || st.edge, variants = variantNames();
  const themeIcon = THEME === "light" ? "sun" : THEME === "dark" ? "moon" : "monitor";
  const shareMenu: MenuItem[] = [{ id: "bLinkMenu", title: "Copy link", icon: "link", run: () => runCommand("share.link"), disabled: !can("share.link") }, ...exportItems()];
  return <>
    <button id="bSidebar" type="button" class="tb icon" aria-controls="side" aria-expanded={Boolean($("app").classList.contains("sidebar-open"))}
      aria-label="Show or hide the project panels" data-tip="Projects and panels" onClick={() => runCommand("app.sidebar")}><Icon name="sidebar" /></button>
    <div class="docTitle">
      <svg class="mark" width="20" height="20" viewBox="0 0 20 20" aria-hidden="true"><rect x="1" y="1" width="18" height="18" rx="5" fill="var(--accent-bg)" />
        <path d="M6 14.5V5.5h7M6 10h5" stroke="var(--accent-text)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" /><circle cx="14" cy="14" r="1.6" fill="var(--accent-text)" /></svg>
      <span class="title" id="fname" title={DOC_TITLE}>{DOC_TITLE}</span>
      {DOC ? <Btn id="bAbout" cmd="app.about" icon="info" cls="ghost" /> : null}
    </div>
    {S ? <div class="tgroup" role="group" aria-label="View">
      {boardKind ? <div class="seg" role="group" aria-label="2D or 3D">
        <Btn id="b2d" icon="plane" text="2D" tip="2D view" keys={keysOf("view.3d")} pressed={!st.mode3d} onClick={() => { if (st.mode3d) runCommand("view.3d"); }} />
        <Btn id="b3d" icon="cube" text="3D" tip="3D view" keys={keysOf("view.3d")} pressed={st.mode3d} onClick={() => { if (!st.mode3d) runCommand("view.3d"); }} />
      </div> : null}
      {can("view.fit") ? <Btn id="bFit" cmd="view.fit" icon="fit" text="Fit" /> : null}
      {can("view.flip") ? <span class="split">
        <Btn id="bFlip" cmd="view.flip" icon="flip" text={view.mirror ? "Bottom" : "Top"} tip={view.mirror ? "Viewed from below: view from above" : "Viewed from above: view from below"} pressed={view.mirror} />
        <Menu id="bFlipMenu" label="Other side opacity" icon="chevDown" cls="caretOnly" panel={OpacityPanel} />
      </span> : null}
    </div> : null}
    {flat ? <div class="tgroup" role="group" aria-label="Tools">
      <span class="split">
        <Btn id="bMeasure" icon={st.edge ? "gap" : "ruler"} text={st.edge ? "Edge gap" : "Measure"} pressed={measuring}
          tip={st.edge ? "Edge gap: the gap between the edges of two objects" : "Measure a distance; snaps to pad centres, vertices, then edges (hold Alt: no snap)"}
          keys={st.edge ? keysOf("tools.edge") : keysOf("tools.measure")} onClick={() => runCommand(st.edge ? "tools.edge" : "tools.measure")} />
        {can("tools.edge") ? <Menu id="bMeasureMenu" label="Measure mode" icon="chevDown" cls="caretOnly" items={[
          { id: "bPoint", title: "Point to point", icon: "ruler", keys: keyLabel("M"), checked: st.measure, run: () => { if (!st.measure) runCommand("tools.measure"); } },
          { id: "bEdge", title: "Edge gap", icon: "gap", keys: keyLabel("Shift+M"), checked: st.edge, run: () => { if (!st.edge) runCommand("tools.edge"); } },
        ]} /> : null}
      </span>
      <Btn id="bMark" cmd="tools.mark" icon="pin" text="Mark" tip="Drop a review mark with a note" pressed={!!st.marking} />
      <button id="bUnit" type="button" class="tb unit" aria-label={`Units: ${UNIT === "mm" ? "millimetres" : "mil"}; switch`} data-tip="Units: millimetres or mil"
        data-keys={keysOf("tools.units")} aria-keyshortcuts="Q" onClick={() => runCommand("tools.units")}><Icon name="units" /><span class="lbl unitv">{UNIT}</span></button>
    </div> : null}
    {DOC ? <div class="tgroup share" role="group" aria-label="Share">
      <Btn id="bLink" cmd="share.link" icon="link" text="Copy link" tip="Copy a link to this view: document, selection, zoom and unit" />
      {flat ? <Menu id="bExport" label="Export" icon="download" text="Export" caret items={exportItems()} tip="Export: save as SVG or print" /> : null}
    </div> : null}
    <div class="tspacer"></div>
    {runs ? <Btn id="bRun" cmd="app.run" icon="play" text="Run checks" cls="runBtn" disabled={!!RUNS.job}
      tip={RUNS.job ? "A run is in progress" : "Run checks on this server (read-only; nothing is written)"} /> : null}
    {variants.length ? <select id="variantSel" class="tbSelect" aria-label="Assembly variant" data-tip="The project's assembly variant"
      onChange={e => setVariant((e.target as HTMLSelectElement).value)}>
      <option value="" selected={!VARIANT}>[No Variations]</option>{variants.map(n => <option selected={n === VARIANT}>{n}</option>)}
    </select> : null}
    <div class="searchBox" role="search">
      <Icon name="search" />
      <input id="search" placeholder="Search or run…" aria-label="Search parts, nets, documents and commands" autocomplete="off" spellcheck={false}
        onKeyDown={e => { const t = e.target as HTMLInputElement; if (e.key === "Enter") { const q = t.value; t.value = ""; if (q.trim()) openPalette(q); else find(q); t.blur(); } else if (e.key === "Escape") t.blur(); else if (e.key === "ArrowDown") { e.preventDefault(); openPalette(t.value); t.value = ""; } }}
        onInput={e => { const t = e.target as HTMLInputElement; const q = t.value; t.value = ""; openPalette(q); }} />
      <kbd class="searchKey" onClick={() => openPalette()}>{keyLabel("Mod+K")}</kbd>
    </div>
    <span class="tgroup end">
      <Menu id="bMore" label="More" icon="more" cls="onlyNarrow" align="right" items={shareMenu} tip="Share and export" />
      <Menu id="bTheme" label="Interface theme" icon={themeIcon} align="right" tip="Interface theme" items={[
        { heading: "Interface theme" },
        { id: "themeSystem", title: "Follow the system", icon: "monitor", radio: true, checked: THEME === "system", run: () => runCommand("app.theme.system") },
        { id: "themeLight", title: "Light", icon: "sun", radio: true, checked: THEME === "light", run: () => runCommand("app.theme.light") },
        { id: "themeDark", title: "Dark", icon: "moon", radio: true, checked: THEME === "dark", run: () => runCommand("app.theme.dark") },
      ]} />
      <Btn id="bKeys" cmd="app.shortcuts" icon="keyboard" cls="hideNarrow" />
      {S ? <Btn id="bDock" cmd="view.dock" icon="dock" tip={dockNarrow() ? "Properties" : "Show or hide the inspector"} pressed={dockNarrow() ? DOCK.sheet : DOCK.open} /> : null}
    </span>
  </>;
}
export var TOOLBAR_READY = false;   // var: read before this module runs by the modules that come first
export function toolbarReady() { TOOLBAR_READY = true; refreshToolbar(); }
export function refreshToolbar() { if (TOOLBAR_READY) preact.render(<Toolbar />, $("top")); }
