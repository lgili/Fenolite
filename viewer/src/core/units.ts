// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { draw } from "../board/draw";
import { select } from "../board/info";
import { showInfo } from "./dom";
import { showCoord } from "./input";
import { S, st } from "./state";
import { LIB, LIBSEL, buildLibList, itemInfo } from "../library/library";
import { selectNet } from "../sch/project-nets";
import { SCH, isSch } from "../sch/scene";
import { schSelect } from "../sch/select";
import { $ } from "./dom";
// ================================================================== units: millimetres or mil (Q), as in Altium
export const MIL_MM = 0.0254;
export let UNIT = (() => { try { return localStorage.getItem("fenolite.view.unit") === "mil" ? "mil" : "mm"; } catch (e) { return "mm"; } })();
export function fmtLen(mm) { return UNIT === "mil" ? `${(mm / MIL_MM).toFixed(2)} mil` : `${mm.toFixed(3)} mm`; }
export function fmtNm(nm) { return fmtLen(nm / 1e6); }
export function fmtPair(a, b) { return UNIT === "mil" ? `${(a / MIL_MM).toFixed(2)} × ${(b / MIL_MM).toFixed(2)} mil` : `${a.toFixed(3)} × ${b.toFixed(3)} mm`; }

export function setUnit(u) {
  UNIT = u; $("bUnit").textContent = u; try { localStorage.setItem("fenolite.view.unit", u); } catch (e) { /* the choice is kept for this page only */ }
  if (!S) return;
  if (LIB && st.itemInfo && LIBSEL >= 0 && !st.lastHit && SCH.sel < 0) showInfo(itemInfo(LIB.items[LIBSEL]));
  if (isSch()) { if (SCH.sel >= 0) schSelect(SCH.sel); else if (SCH.selNet >= 0) selectNet(SCH.selNet, false); }
  else if (st.lastHit) select(st.lastHit, st.lastAt);
  if (st.mouse) showCoord(st.mouse[0], st.mouse[1]);
  buildLibList(); draw();
}
$("bUnit").onclick = () => setUnit(UNIT === "mm" ? "mil" : "mm");
$("bUnit").textContent = UNIT;
