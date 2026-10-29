// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The status bar (c0268, design decision 6), left to right: the cursor position in the page unit, the grid pitch
// when a grid is drawn, the zoom, the current layer, the selection, then the unit and the live state. The file's
// digest is not here: it is in "About this document". The spans keep their ids (coord, zoomv, cur, live): the
// tools write the cursor, the measure and the live state into them as they always did.
import * as preact from "preact";
import { $ } from "../core/dom";
import { S, st } from "../core/state";
import { fmtLen, UNIT } from "../core/units";
import { isSch, SCH } from "../sch/scene";
import { Icon } from "../ui/icons";

export function StatusBar() {
  return <>
    <span class="sItem sCoord"><Icon name="target" size={12} /><span id="coord">x — y —</span></span>
    <span class="sItem" id="gridv" hidden></span>
    <span class="sItem" id="zoomv"></span>
    <span class="sItem" id="cur"></span>
    <span class="sItem sSel" id="selv"></span>
    <span class="sSpacer"></span>
    <span class="sItem" id="unitv" title="Page unit (Q)"></span>
    <span class="sItem sLive" id="live"></span>
  </>;
}
preact.render(<StatusBar />, $("status"));
export function statusText(id: string, text: string) { const el = $(id); if (!el) return; el.textContent = text; el.hidden = !text; }
export function refreshStatus() {   // the parts the page does not write as it goes: unit, grid and selection
  statusText("unitv", S && S.kind !== "table" ? (UNIT === "mm" ? "Millimetres" : "Mil") : "");
  statusText("gridv", S && isSch() && S.sheet.grid ? `Grid ${fmtLen(S.sheet.grid)}` : "");
  let sel = "";
  if (S && isSch()) sel = SCH.selComp >= 0 ? `Part ${S.comps[SCH.selComp].ref}` : SCH.selNet >= 0 ? `Net ${S.nets[SCH.selNet].name || "(no name)"}` : "";
  else if (S && !S.kind && S.comps) {
    if (st.selComp >= 0) sel = `Part ${S.comps[st.selComp].ref}`;
    else if (st.selNet >= 0) sel = `Net ${S.nets[st.selNet]}`;
    else if (st.query && (st.query.comps.length || st.query.prims.size)) sel = `Filter: ${st.query.comps.length} part(s) · ${st.query.prims.size} item(s)`;
  }
  statusText("selv", sel);
}
