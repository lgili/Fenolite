// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The shortcut sheet (c0300, design decision 2): `?` prints every command of the registry that has a shortcut,
// by group, with whether it applies to what is shown, and the pointer gestures of the drawing.
import * as preact from "preact";
import { available, COMMANDS, keyLabel } from "../core/commands";
import { $ } from "../core/dom";
import { Icon } from "../ui/icons";

const GESTURES = [["Wheel", "Zoom at the pointer"], ["Drag", "Pan (2D) · orbit (3D)"], ["Shift drag", "Pan (3D)"], ["Click", "Select a part, a pad or a net"],
  ["Double-click", "Open a sheet symbol · show the part on the other document"], ["Alt while measuring", "No snapping"]];
export function ShortcutSheet() {
  const groups = new Map();
  for (const c of COMMANDS) { const keys = c.keys.filter(k => k !== "=" && k !== "_"); if (!keys.length) continue;
    if (!groups.has(c.group)) groups.set(c.group, []); groups.get(c.group).push([c, keys]); }
  return <>
    <header class="dlgHead"><h2 id="keysTitle"><Icon name="keyboard" /> Keyboard shortcuts</h2>
      <button type="button" class="tb icon ghost" aria-label="Close" data-tip="Close" onClick={() => $("shortcuts").close()}><Icon name="x" /></button></header>
    <div class="keysGrid">
      {[...groups].map(([g, list]) => <section key={g}><h3>{g}</h3><dl>
        {list.map(([c, keys]) => <div class={available(c) ? "" : "na"} title={available(c) ? "" : "Not available in this view"}>
          <dt>{c.title}</dt><dd>{keys.map((k, i) => <>{i ? <span class="or">or</span> : null}<kbd>{keyLabel(k)}</kbd></>)}</dd></div>)}
      </dl></section>)}
      <section><h3>Pointer</h3><dl>{GESTURES.map(([k, v]) => <div><dt>{v}</dt><dd><kbd>{k}</kbd></dd></div>)}</dl></section>
    </div>
    <p class="dlgFoot">Shortcuts do not act while a text field has the focus; {keyLabel("Mod+K")} opens the palette from anywhere.</p>
  </>;
}
export function openShortcuts() {
  const dlg = $("shortcuts"); preact.render(<ShortcutSheet />, dlg);
  if (!dlg.open) dlg.showModal();
  (dlg.querySelector("button") as HTMLElement)?.focus();
}
$("shortcuts").addEventListener("click", e => { if (e.target === $("shortcuts")) $("shortcuts").close(); });
