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
import { imodel, irow, isection } from "../inspect/model";
import { inspect } from "../panels/inspector";
import { projectNetSection, schNetSection } from "./project-nets";
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
  if (o.comp >= 0 && o.k === "comp") SCH.selComp = o.comp;
  if (o.k !== "comp" && o.net >= 0) { SCH.selNet = o.net; const n = S.nets[o.net]; shareNet(n.project || n.name); }
  inspect(() => schModel(oi));
  buildNav(); draw();
}
const SCH_KIND = { comp: "component", wire: "wire", pin: "pin", sheet: "sheet" };
export function schModel(oi) {   // c0301: the inspector model of an object of a sheet
  const o = S.objects[oi], sections = [];
  if (o.k === "comp") sections.push(isection("Component", compRows(o.comp).map(([k, v]) => irow(k, v, /^https?:\/\//i.test(String(v)) ? { link: String(v) } : undefined))));
  else {
    sections.push(isection("Properties", (o.info || []).map(([k, v]) => irow(k, v, /^https?:\/\//i.test(String(v)) ? { link: String(v) } : undefined))));
    if (o.net >= 0) { const n = S.nets[o.net]; sections.push(schNetSection(n), projectNetSection(n)); }
    if (o.comp >= 0) sections.push(isection("Part", compRows(o.comp).map(([k, v]) => irow(k, v))));
  }
  const ci = o.comp >= 0 ? o.comp : -1, title = o.k === "comp" ? S.comps[o.comp].ref : (o.info || []).find(r => /^(Name|Text|Designator)$/.test(r[0]))?.[1] || o.k;
  return imodel(SCH_KIND[o.k] || "item", String(title), sections, { subtitle: o.k === "comp" ? S.comps[o.comp].comment || "" : o.k, target: { sch: true, comp: ci, net: o.net >= 0 ? o.net : -1 } });
}
export function netBox(ni) { let b = null; for (const o of S.objects) if (o.net === ni && o.b) b = b ? [Math.min(b[0], o.b[0]), Math.min(b[1], o.b[1]), Math.max(b[2], o.b[2]), Math.max(b[3], o.b[3])] : [...o.b]; return b; }
