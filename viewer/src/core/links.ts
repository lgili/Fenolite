// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ---- deep links: the URL's hash keeps the document, the selection, the view, the unit and the layer
import { draw } from "../board/draw";
import { buildTabs } from "../board/tabs";
import { LIB, LIBSEL } from "../library/library";
import { isSch, SCH } from "../sch/scene";
import { $ } from "./dom";
import { PREVIEW_MODE } from "./env";
import { find } from "./input";
import { DOC, S, st, view, vis } from "./state";
import { setUnit, UNIT } from "./units";
import { fitted, setFitted } from "./viewport";
export function selName() {
  if (!S) return "";
  if (isSch()) return SCH.selComp >= 0 ? S.comps[SCH.selComp].ref : SCH.selNet >= 0 ? "net:" + S.nets[SCH.selNet].name : "";
  return st.selComp >= 0 ? S.comps[st.selComp].ref : st.selNet >= 0 ? "net:" + S.nets[st.selNet] : "";
}
export function linkHash() { if (!DOC) return "";
  const q = new URLSearchParams({ doc: DOC.id }); const sel = selName(); if (sel) q.set("sel", sel);
  if (PREVIEW_MODE) { q.set("preview","1"); if (LIB && LIBSEL >= 0) q.set("item",LIB.items[LIBSEL].name); }
  q.set("z", view.s.toFixed(3)); q.set("c", `${view.cx.toFixed(4)},${view.cy.toFixed(4)}`); q.set("u", UNIT);
  if (!isSch() && st.cur) q.set("l", st.cur); return q.toString(); }
export let linkTimer = null, linkReady = false;
export function setLinkReady(v) { linkReady = v; }
export function linkLater() { if (!linkReady) return; clearTimeout(linkTimer); linkTimer = setTimeout(() => { const h = linkHash(); if (h && location.hash.slice(1) !== h) try { history.replaceState(null, "", "#" + h); } catch (e) { /* a sandboxed frame */ } }, 400); }
export function applySelect(name) { if (!name || !S) return; const n = name.startsWith("net:") ? name.slice(4) : name; find(n); }
export function applyLink(q) {   // after the document of the link is open
  if (q.get("u") === "mil" || q.get("u") === "mm") setUnit(q.get("u"));
  if (q.get("l") && S && S.layers && S.layers.some(l => l.id === q.get("l"))) { st.cur = q.get("l"); vis.set(st.cur, true); buildTabs(); }
  if (q.get("sel")) applySelect(q.get("sel"));
  const z = parseFloat(q.get("z")), c = (q.get("c") || "").split(",").map(Number);
  if (z > 0 && c.length === 2 && c.every(Number.isFinite)) { view.s = z; view.cx = c[0]; view.cy = c[1]; setFitted(true); }
  draw();
}
$("bLink").onclick = async () => { const h = linkHash(); try { history.replaceState(null, "", "#" + h); } catch (e) { /* ignore */ }
  try { await navigator.clipboard.writeText(location.href); $("live").textContent = "link copied"; } catch (e) { window.prompt("Link to this view", location.href); } };
