// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== units: millimetres or mil (Q), as in Altium
import { draw } from "../board/draw";
import { select } from "../board/info";
import { buildLibList, itemInfo, LIB, LIBSEL } from "../library/library";
import { selectNet } from "../sch/project-nets";
import { isSch, SCH } from "../sch/scene";
import { schSelect } from "../sch/select";
import { $, showInfo } from "./dom";
import { showCoord } from "./input";
import { refreshStatus } from "../panels/status-bar";
import { refreshToolbar } from "../panels/toolbar";
import { S, st } from "./state";
import { refreshInspector, refreshSummary } from "../panels/inspector";
export const MIL_MM = 0.0254;
export let UNIT = (() => { try { return localStorage.getItem("fenolite.view.unit") === "mil" ? "mil" : "mm"; } catch (e) { return "mm"; } })();
export function fmtLen(mm) { return UNIT === "mil" ? `${(mm / MIL_MM).toFixed(2)} mil` : `${mm.toFixed(3)} mm`; }
export function fmtNm(nm) { return fmtLen(nm / 1e6); }
export function fmtXY(a, b) { return UNIT === "mil" ? `${(a / MIL_MM).toFixed(2)}, ${(b / MIL_MM).toFixed(2)} mil` : `${a.toFixed(3)}, ${b.toFixed(3)} mm`; }   // a position (c0301)
export function fmtPair(a, b) { return UNIT === "mil" ? `${(a / MIL_MM).toFixed(2)} × ${(b / MIL_MM).toFixed(2)} mil` : `${a.toFixed(3)} × ${b.toFixed(3)} mm`; }

export function setUnit(u) {
  UNIT = u; refreshToolbar(); refreshStatus(); try { localStorage.setItem("fenolite.view.unit", u); } catch (e) { /* the choice is kept for this page only */ }
  if (!S) return;
  refreshInspector(); refreshSummary();   // c0301: the selection's model is built again in the new unit
  if (st.mouse) showCoord(st.mouse[0], st.mouse[1]);
  buildLibList(); draw();
}
