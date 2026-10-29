// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { draw } from "../board/draw";
import { VARIANT, variantOf } from "../board/variants";
import { esc, linkify, showInfo } from "../core/dom";
import { S } from "../core/state";
import { fmtPair } from "../core/units";
import { buildNav } from "../panels/navigator";
import { projectNetInfo, shareNet } from "./project-nets";
import { SCH } from "./scene";
export function rows(list) { return `<table>${list.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${linkify(v)}</td></tr>`).join("")}</table>`; }
export function compRows(ci) { const c = S.comps[ci]; const r = [["Designator", c.ref], ["Comment", c.comment], ["Design Item ID", c.lib]];
  if (c.b) r.push(["Extent", fmtPair(c.b[2] - c.b[0], c.b[3] - c.b[1])]);
  if (c.description) r.push(["Description", c.description]); if (c.footprint) r.push(["Footprint", c.footprint]);
  const vs = variantOf(c.group || c.ref);
  const params = { ...(c.params || {}), ...((vs && vs.params) || {}) };
  for (const [k, v] of Object.entries(params)) r.push([k, v]);
  if (vs) r.push([`Variant ${VARIANT}`, vs.kind]); return r; }
export function schSelect(oi) {
  SCH.sel = oi; SCH.selNet = -1; SCH.selComp = -1;
  if (oi < 0) { showInfo(null); buildNav(); draw(); return; }
  const o = S.objects[oi];
  if (o.k === "comp") { SCH.selComp = o.comp; showInfo(`<b>Properties</b> · Component${rows(compRows(o.comp))}`); }
  else { if (o.net >= 0) SCH.selNet = o.net;
    let html = `<b>Properties</b> · ${esc(o.k)}${rows(o.info)}`;
    if (o.net >= 0) { const n = S.nets[o.net]; html += `<br><b>Net ${esc(n.name || "(no name)")}</b>: ${n.pins.length} pins` + (n.pins.length ? `<br><small>${esc(n.pins.slice(0, 40).join(", "))}${n.pins.length > 40 ? " …" : ""}</small>` : "") + projectNetInfo(n); shareNet(n.project || n.name); }
    if (o.comp >= 0) html += `<br><br><b>Part</b>${rows(compRows(o.comp))}`;
    showInfo(html); }
  buildNav(); draw();
}
export function netBox(ni) { let b = null; for (const o of S.objects) if (o.net === ni && o.b) b = b ? [Math.min(b[0], o.b[0]), Math.min(b[1], o.b[1]), Math.max(b[2], o.b[2]), Math.max(b[3], o.b[3])] : [...o.b]; return b; }
