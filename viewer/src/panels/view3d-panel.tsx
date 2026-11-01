// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The 3D panel (c0301, design decision 6): the dock's tab in 3D instead of Layers: the camera views (the view
// cube's six faces and iso), what is drawn (bodies, board, silkscreen and copper textures) and Reset view.
import * as preact from "preact";
import { $ } from "../core/dom";
import { S } from "../core/state";
import { camPreset, set3DOption, V3 } from "../three/view3d";
import { Icon } from "../ui/icons";

const VIEWS = [["top", "Top"], ["front", "Front"], ["left", "Left"], ["iso", "Iso"], ["bottom", "Bottom"], ["back", "Back"], ["right", "Right"]];
const TOGGLES = [["bodies", "Bodies", "Parts: models, else outlines extruded to their height"], ["board", "Board", "The board slab and its edge"],
  ["silk", "Silkscreen", "The silkscreen of both faces"], ["copper", "Copper", "The copper of both faces"]];
export function View3DPanel() {
  const bodies = (S && S.bodies) || [], models = bodies.filter(b => b.render === "model" || b.render === "fitted").length;
  return <div class="p3d">
    <section class="lgroup"><div class="lgHead"><span class="lgTitle">Camera</span></div>
      <div class="viewGrid">{VIEWS.map(([id, title]) => <button type="button" id={`v3${id}`} class="tb small" onClick={() => camPreset(id, true)}>{title}</button>)}
        <button type="button" id="v3reset" class="tb small" data-tip="The iso view, fitted to the board" onClick={() => camPreset("iso", true)}><Icon name="refresh" size={14} /><span class="lbl">Reset</span></button></div>
      <p class="hint">Drag to orbit, Shift+drag to pan, wheel to zoom; the cube at the top right turns the view too.</p>
    </section>
    <section class="lgroup"><div class="lgHead"><span class="lgTitle">Show</span></div>
      {TOGGLES.map(([key, title, note]) => <label class="tog" title={note}>
        <input type="checkbox" id={`c3${key}`} checked={!!V3[key]} onChange={e => { set3DOption(key, (e.target as HTMLInputElement).checked); build3DPanel(); }} />
        <span>{title}</span><small>{note}</small></label>)}
    </section>
    <p class="hint">{bodies.length ? `${bodies.length} bodies: ${models} with a model, ${bodies.length - models} extruded.` : "No part body on this board."}</p>
  </div>;
}
export function build3DPanel() { preact.render(<View3DPanel />, $("dock3d")); }
