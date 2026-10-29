// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== review panels (c0187): filter, highlight, components, nets
import * as preact from "preact";
import { byLayer, qCache } from "../board/cache";
import { draw } from "../board/draw";
import { compInfo } from "../board/info";
import { queryParse, queryRun, similarQuery } from "../board/query";
import { $, esc, natural, showInfo } from "../core/dom";
import { MM, S, st } from "../core/state";
import { fmtLen } from "../core/units";
import { fit } from "../core/viewport";
import { shareNet } from "../sch/project-nets";
import { set3D } from "../three/view3d";
import { Icon } from "../ui/icons";
import { showSection } from "../ui/section";
import { Empty } from "../ui/states";
import { netModel, partModel } from "../inspect/model";
import { inspect } from "./inspector";
export const HL_ALPHA = { dim: 0.22, mask: 0.06, normal: 1 };   // c0269: Dim at 0.22
export const ROW = 24;
export function vlist(box, items, row, click, selected, empty?) {   // a list that draws only the rows in view (Preact rows, c0268)
  box.style.height = items.length ? `${Math.min(240, items.length * ROW + 4)}px` : "auto";
  if (!items.length) { box.onscroll = null; preact.render(<Empty text={empty || "Nothing to list."} />, box); return; }
  const paint = () => { const top = box.scrollTop, h = box.clientHeight || 240;
    const a = Math.max(0, Math.floor(top / ROW) - 4), z = Math.min(items.length, Math.ceil((top + h) / ROW) + 4), rows = [];
    for (let i = a; i < z; i++) rows.push(<div key={i} class={"navi vrow" + (selected(items[i]) ? " sel" : "")} style={`top:${i * ROW}px;height:${ROW}px;line-height:${ROW}px`}
      onClick={() => click(items[i])}>{row(items[i])}</div>);
    preact.render(<div class="vinner" style={`height:${items.length * ROW}px`}>{rows}</div>, box); };
  box.onscroll = paint; paint();
}
export function netBounds(ni) { let b = null;
  for (const list of byLayer.values()) for (const [pr, q] of list) if (pr[3] === ni) b = b ? [Math.min(b[0], q[0]), Math.min(b[1], q[1]), Math.max(b[2], q[2]), Math.max(b[3], q[3])] : [...q];
  return b; }
export function primBounds(set) { let b = null;
  for (const list of byLayer.values()) for (const [pr, q] of list) if (set.has(pr)) b = b ? [Math.min(b[0], q[0]), Math.min(b[1], q[1]), Math.max(b[2], q[2]), Math.max(b[3], q[3])] : [...q];
  return b; }
export function selectCompAt(ci) { if (st.mode3d) set3D(false); st.selComp = ci; st.selNet = -1; const b = S.comps[ci].bbox; if (b) fit([b[0] - 5, b[1] - 5, b[2] + 5, b[3] + 5]); inspect(() => partModel(ci)); buildReview(); draw(); }
export function selectNetAt(ni) { if (st.mode3d) set3D(false); st.selNet = ni; st.selComp = -1; shareNet(S.nets[ni]); const b = netBounds(ni); if (b) fit([b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3]);
  inspect(() => netModel(ni)); buildReview(); draw(); }
const COMP_SORT = { ref: c => c.ref, value: c => String(c.value || ""), footprint: c => String(c.footprint || "") };
export function buildReview() {
  if (!S || S.kind || !S.prims) return; const qy = st.query, inQ = qy ? new Set(qy.comps) : null;
  const cfRaw = $("compFilter").value.trim(), nfRaw = $("netFilter").value.trim(), cf = cfRaw.toLowerCase(), nf = nfRaw.toLowerCase();
  const key = COMP_SORT[$("compSort").value] || COMP_SORT.ref;
  const comps = S.comps.map((c, i) => i).filter(i => !inQ || inQ.has(i)).filter(i => { const c = S.comps[i]; return !cf || [c.ref, c.value, c.footprint].some(v => String(v || "").toLowerCase().includes(cf)); })
    .sort((a, b) => natural(key(S.comps[a]), key(S.comps[b])) || natural(S.comps[a].ref, S.comps[b].ref));
  let netSet = null; if (qy) { netSet = new Set(); for (const pr of qy.prims) if (pr[3] >= 0) netSet.add(pr[3]); }
  const info = i => (S.netinfo || [])[i] || { pads: 0, length: 0 }, ns = $("netSort").value;
  const nets = S.nets.map((n, i) => i).filter(i => S.nets[i] && (!netSet || netSet.has(i)) && (!nf || S.nets[i].toLowerCase().includes(nf)))
    .sort((a, b) => (ns === "pads" ? info(b).pads - info(a).pads : ns === "length" ? info(b).length - info(a).length : 0) || natural(S.nets[a], S.nets[b]));
  const total = S.nets.filter(Boolean).length;
  showSection("components", true, comps.length === S.comps.length ? comps.length : `${comps.length} / ${S.comps.length}`, "Components");
  showSection("nets", true, nets.length === total ? nets.length : `${nets.length} / ${total}`, "Nets");
  const why = (raw, none, what) => raw ? `No ${what} match “${raw}”.` : qy ? `No ${what} in the filter’s result.` : none;
  vlist($("compList"), comps, i => { const c = S.comps[i]; return <><b>{c.ref}</b><small>{[c.value, c.footprint, c.side === "bottom" ? "bottom" : ""].filter(Boolean).join(" · ")}</small></>; },
    selectCompAt, i => i === st.selComp, why(cfRaw, "No components on this board.", "components"));
  vlist($("netList"), nets, i => { const n = (S.netinfo || [])[i]; return <><b>{S.nets[i]}</b>{n ? <small>{`${n.pads} pads · ${fmtLen(n.length * MM)}`}</small> : null}</>; },
    selectNetAt, i => i === st.selNet, why(nfRaw, "No nets on this board.", "nets"));
  $("queryInfo").textContent = qy ? (qy.prims.size || qy.comps.length ? `${qy.comps.length} part(s) · ${qy.prims.size} primitive(s)` : "Nothing matches the filter.") : "";
}
export function applyQuery(text, zoom) {
  if (!S || S.kind || !S.prims) return; text = text.trim();
  if (!text) { clearQuery(); return; }
  st.query = { text, ...queryRun(S, queryParse(text)) }; qCache.delete(text); buildReview();
  if (zoom && st.query.prims.size) { const b = primBounds(st.query.prims); if (b) fit([b[0] - 3, b[1] - 3, b[2] + 3, b[3] + 3]); }
  draw();
}
export function clearQuery() { st.query = null; $("query").value = ""; st.selNet = -1; st.selComp = -1; showInfo(null); buildReview(); draw(); }
export let qTimer = null;
$("query").addEventListener("input", e => { clearTimeout(qTimer); qTimer = setTimeout(() => applyQuery(e.target.value, false), 250); });
$("query").addEventListener("keydown", e => { if (e.key === "Enter") { clearTimeout(qTimer); applyQuery(e.target.value, true); } else if (e.key === "Escape") e.target.blur(); });
$("compFilter").addEventListener("input", buildReview); $("netFilter").addEventListener("input", buildReview);
$("compSort").addEventListener("change", buildReview); $("netSort").addEventListener("change", buildReview);
preact.render(<Icon name="x" />, $("bQClear"));
export function findSimilar() { if (!S || S.kind) return; const h = st.lastHit, ci = st.selComp >= 0 ? st.selComp : -1;
  const text = similarQuery(S, h ? h.pr : null, ci >= 0 ? ci : h && h.pr[4] >= 0 && h.pr[3] < 0 ? h.pr[4] : -1);
  if (!text) { $("queryInfo").textContent = "Select a part or a primitive first."; return; }
  $("query").value = text; applyQuery(text, false); }
$("bSimilar").onclick = findSimilar;
$("bQClear").onclick = clearQuery;
$("hlMode").value = HL_ALPHA[st.hl] !== undefined ? st.hl : "dim";
$("hlMode").onchange = e => { st.hl = e.target.value; try { localStorage.setItem("fenolite.view.highlight", st.hl); } catch (err) { /* private window */ } draw(); };
