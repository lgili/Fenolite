// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { esc, linkify, showInfo } from "../core/dom";
import { S, st } from "../core/state";
import { fmtLen, fmtNm, fmtPair, MIL_MM } from "../core/units";
import { shareNet } from "../sch/project-nets";
import { draw } from "./draw";
import { VARIANT, variantOf } from "./variants";
export function compInfo(ci) { const c = S.comps[ci], b = c.bbox, vs = variantOf(c.ref);
  const params = { ...(c.params || {}), ...((vs && vs.params) || {}) };   // c0187: every parameter the file holds
  return `<b>${esc(c.ref)}</b> · ${esc(c.side)} · rot ${c.rotation}°<br>Footprint: ${esc(c.footprint)}${c.value ? `<br>Value: ${esc(c.value)}` : ""}<br>Position: (${fmtLen(c.x)}, ${fmtLen(c.y)})` +
  (b ? `<br>Extent: ${fmtPair(b[2] - b[0], b[3] - b[1])}` : "") + (vs ? `<br>Variant ${esc(VARIANT)}: <b>${esc(vs.kind)}</b>` : "") +
  Object.entries(params).map(([k, v]) => { const mil = /^(-?\d+(?:\.\d+)?)mil$/.exec(String(v));   // an Altium length, in the page's unit
    return `<br>${esc(k)}: ${mil ? fmtLen(+mil[1] * MIL_MM) : linkify(v)}`; }).join(""); }
export function padOf(label, x, y) {   // the pad entry of a primitive's label nearest the point
  let best = null, bd = Infinity; for (const p of S.pads || []) { if (p.label !== label.replace(/ (hole|slot)$/, "")) continue; const d = Math.hypot(p.x - x, p.y - y); if (d < bd) { bd = d; best = p; } } return best; }
export function layerName(id) { const l = S.layers.find(x => x.id === id); return l ? l.name : id; }
export function padInfo(p) {
  const r = [`<br><b>Pad ${esc(p.number)}</b> · ${esc(p.shape || "?")} · ${esc(p.kind)}`];
  if (p.w != null) r.push(`Size: ${fmtPair(p.w / 1e6, p.h / 1e6)}`);
  if (p.ratio != null && p.w != null) r.push(`Corner radius: ${fmtNm(p.ratio / 1e6 * Math.min(p.w, p.h))}`);
  if (p.drill != null) r.push(`Hole Ø ${fmtNm(p.drill)}` + (p.slot ? ` · slot ${fmtNm(p.slot + p.drill)} long` : ""));
  r.push(`Centre: (${fmtLen(p.x)}, ${fmtLen(p.y)}) · rot ${(+p.rot).toFixed(1)}°`);
  if (p.layers && p.layers.length) r.push(`Layers: ${esc(p.layers.map(layerName).join(", "))}`);
  if (p.mask != null) r.push(`Solder mask expansion: ${fmtNm(p.mask)} · ${esc(p.mask_src)}`);   // c0181: an Altium pad
  if (p.paste != null) r.push(`Paste expansion: ${fmtNm(p.paste)} · ${esc(p.paste_src)}`);
  if (p.mask != null && p.w != null) r.push(`Mask opening: ${fmtPair(Math.max(p.w + 2 * p.mask, 0) / 1e6, Math.max(p.h + 2 * p.mask, 0) / 1e6)}`);
  return r.join("<br>");
}
export function select(h, at?) {
  st.selFinding = -1; st.selNet = -1; st.selComp = -1; st.lastHit = h; st.lastAt = at;
  if (!h) { showInfo(null); draw(); return; }
  const pr = h.pr, net = pr[3], ci = pr[4];
  let html = `<b>${esc(pr[5] || h.layer.name)}</b><br>Layer: ${esc(h.layer.name)}`;
  if (net >= 0) { html += `<br>Net: <b>${esc(S.nets[net])}</b>`; st.selNet = net; shareNet(S.nets[net]); }
  if (ci >= 0) { html += `<br>${compInfo(ci)}`; if (net < 0) st.selComp = ci; }
  if (pr[1] === "s") html += `<br>Width: ${fmtLen(pr[2][4])} · length ${fmtLen(Math.hypot(pr[2][2] - pr[2][0], pr[2][3] - pr[2][1]))}`;
  if (pr[1] === "a") html += `<br>Width: ${fmtLen(pr[2][6])}` + (pr[6] ? ` · radius ${fmtLen(pr[6].r)}` : "");
  const pad = pr[5] && at ? padOf(pr[5], at[0], at[1]) : null;
  if (pad) html += padInfo(pad);
  else if (pr[1] === "c" && h.layer.id === "View.Drill") html += `<br>Hole Ø ${fmtLen(2 * pr[2][2])}`;
  else if (pr[1] === "c") html += `<br>Diameter: ${fmtLen(2 * pr[2][2])}`;
  showInfo(html); draw();
}
