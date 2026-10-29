// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the Layers panel (c0301, design decision 5)
// The dock's Layers tab, on boards and footprints: the layers of tabLayers() in groups (copper, mask and paste,
// silkscreen, mechanical and fabrication, view), each row with its swatch, its full name (wrapped, never cut),
// whether it is current, an opacity slider (l.alpha) and its visibility; a group's header shows or hides the
// group. The layer sets of #lsmenu are the presets, with "Current layer only" (Shift+S). Sheet tabs stay in the
// bottom bar.
import * as preact from "preact";
import { draw } from "../board/draw";
import { setCurrent, SETS, tabLayers } from "../board/tabs";
import { $ } from "../core/dom";
import { S, st, vis } from "../core/state";
import { Icon } from "../ui/icons";
import { RoleLayers } from "./roles";

export const LAYER_GROUPS = [["copper", "Copper"], ["mask", "Mask and paste"], ["silk", "Silkscreen"], ["mech", "Mechanical and fabrication"], ["view", "View"]];
export function layerGroup(l) {
  if (l.kind === "view" || l.id.startsWith("View.")) return "view";
  if (l.kind === "copper" || /\.Cu$/.test(l.id)) return "copper";
  if (/mask|paste/i.test(l.kind || "") || /\.(Mask|Paste)$/.test(l.id)) return "mask";
  if (/silk/i.test(l.kind || "") || /\.SilkS$/.test(l.id)) return "silk";
  return "mech";
}
function relayer() { buildLayers(); draw(); }
function setVisible(id, on) { vis.set(id, on); relayer(); }
function setGroup(ids, on) { for (const id of ids) vis.set(id, on); relayer(); }
export function LayersPanel() {
  const layers = tabLayers(), by = new Map(LAYER_GROUPS.map(([g]) => [g, []]));
  for (const l of layers) by.get(layerGroup(l)).push(l);
  return <>
    <div class="layerTools">
      <span class="layerHint">{st.single ? "Only the current layer is shown." : `${layers.filter(l => vis.get(l.id)).length} of ${layers.length} layers shown`}</span>
    </div>
    {LAYER_GROUPS.map(([g, title]) => { const list = by.get(g); if (!list.length) return null;
      const shown = list.filter(l => vis.get(l.id)).length;
      return <section class="lgroup" key={g} aria-label={title}>
        <div class="lgHead">
          <span class="lgTitle">{title}</span><span class="lgN">{`${shown}/${list.length}`}</span>
          <button type="button" class="tb icon small ghost" aria-pressed={shown > 0} aria-label={`${shown ? "Hide" : "Show"} the ${title.toLowerCase()} layers`}
            data-tip={`${shown ? "Hide" : "Show"} the group`} onClick={() => setGroup(list.map(l => l.id), !shown)}><Icon name={shown ? "eye" : "eyeOff"} size={14} /></button>
        </div>
        {list.map(l => { const on = !!vis.get(l.id), cur = l.id === st.cur, pct = Math.round((l.alpha ?? 1) * 100);
          return <div key={l.id} class={"lrow" + (cur ? " cur" : "") + (on ? "" : " off")} data-layer={l.id}>
            <button type="button" role="radio" aria-checked={cur} class="lcur" aria-label={`Make ${l.name} the current layer`} data-tip="Current layer"
              onClick={() => setCurrent(l.id)}><span class="radio"></span></button>
            <span class="sw" style={`background:${l.color}`}></span>
            <span class="lname" title={l.name === l.id ? `${l.name} · ${l.kind}` : `${l.name} (${l.id}) · ${l.kind}`} onClick={() => setCurrent(l.id)}>{l.name}</span>
            <input type="range" class="lop" min="0" max="100" step="5" value={pct} aria-label={`Opacity of ${l.name}`} title={`Opacity ${pct} %`}
              onInput={e => { l.alpha = +(e.target as HTMLInputElement).value / 100; draw(); (e.target as HTMLInputElement).title = `Opacity ${Math.round(l.alpha * 100)} %`; }} />
            <button type="button" class="tb icon small ghost leye" aria-pressed={on} aria-label={`${on ? "Hide" : "Show"} ${l.name}`} data-tip={on ? "Hide" : "Show"}
              onClick={() => setVisible(l.id, !on)}><Icon name={on ? "eye" : "eyeOff"} size={14} /></button>
          </div>; })}
      </section>; })}
    <RoleLayers />
  </>;
}
export function buildLayers() {
  const box = $("layerList"); if (!box) return;
  if (!S || S.kind || !S.layers) { preact.render(null, box); return; }
  preact.render(<LayersPanel />, box);
}
export const presetNames = () => [...Object.keys(SETS), "Current layer only"];
