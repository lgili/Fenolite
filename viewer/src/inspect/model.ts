// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the inspector model (c0269, design decision 2)
// What a click hits, as data: {kind, title, subtitle, sections: [{title, rows: [{label, value, copy}]}], target}.
// panels/inspector renders it in the dock. The builders between the markers are pure (the formatters come in as
// arguments) and run under Node in tests/unit/view/test_page.py -k inspector; a value the scene does not hold
// is left out, never shown as 0.
import { layerName, padOf } from "../board/info";
import { VARIANT, variantOf } from "../board/variants";
import { MM, S } from "../core/state";
import { fmtLen, fmtNm, fmtPair, fmtXY, MIL_MM, UNIT } from "../core/units";
import { boardRole } from "../roles/roles";

// ---- inspector model (c0269)
export function irow(label, value, extra?) {
  if (value === undefined || value === null || value === "" || (typeof value === "number" && !Number.isFinite(value))) return null;
  return { label: String(label), value: String(value), copy: true, ...(extra || {}) };
}
export function isection(title, rows, extra?) { const kept = rows.filter(Boolean); return kept.length ? { title, rows: kept, ...(extra || {}) } : null; }
export function imodel(kind, title, sections, extra?) { return { kind, title, sections: sections.filter(Boolean), ...(extra || {}) }; }
export function modelText(m) {   // "Copy all": every section as "label: value" lines
  return [m.title, ...m.sections.map(s => [s.title, ...s.rows.map(r => `${r.label}: ${r.value}`)].join("\n"))].filter(Boolean).join("\n\n");
}
export function padSection(p, f, layerOf) {   // f: {len(mm), nm(nm), pair(mm, mm), xy(mm, mm)}; sizes of a pad entry in nm, its centre in mm
  const hasSize = p.w != null && p.h != null;
  return isection("Pad", [
    irow("Number", p.number), irow("Shape", p.shape), irow("Mounting", p.kind),
    hasSize ? irow("Size", f.pair(p.w / 1e6, p.h / 1e6)) : null,
    p.ratio != null && hasSize ? irow("Corner radius", f.nm(p.ratio / 1e6 * Math.min(p.w, p.h))) : null,
    p.drill != null ? irow("Drill", `Ø ${f.nm(p.drill)}`) : null,
    p.drill != null && p.slot ? irow("Slot length", f.nm(p.slot + p.drill)) : null,
    p.x != null && p.y != null ? irow("Centre", f.xy(p.x, p.y)) : null,
    p.rot != null ? irow("Rotation", `${(+p.rot).toFixed(1)}°`) : null,
    p.layers && p.layers.length ? irow("Layers", p.layers.map(layerOf).join(", ")) : null,
    p.mask != null ? irow("Mask expansion", f.nm(p.mask), { note: p.mask_src }) : null,
    p.mask != null && hasSize ? irow("Mask opening", f.pair(Math.max(p.w + 2 * p.mask, 0) / 1e6, Math.max(p.h + 2 * p.mask, 0) / 1e6)) : null,
    p.paste != null ? irow("Paste expansion", f.nm(p.paste), { note: p.paste_src }) : null,
  ]);
}
export function trackSection(d, layer, f) {   // a segment [x1, y1, x2, y2, width] in mm
  return isection("Track", [irow("Width", f.len(d[4])), irow("Length", f.len(Math.hypot(d[2] - d[0], d[3] - d[1]))), irow("Layer", layer),
    irow("Start", f.xy(d[0], d[1])), irow("End", f.xy(d[2], d[3]))]);
}
export function arcSection(d, a, layer, f) {   // [x1, y1, xm, ym, x2, y2, width] and its circle {r, a1, a3, ccw}
  let span = null;
  if (a) { const T = 2 * Math.PI; span = ((a.a3 - a.a1) % T + T) % T; if (a.ccw) span = T - span; }
  return isection("Arc", [irow("Width", f.len(d[6])), a ? irow("Radius", f.len(a.r)) : null,
    span !== null ? irow("Angle", `${(span * 180 / Math.PI).toFixed(1)}°`) : null, span !== null ? irow("Length", f.len(a.r * span)) : null, irow("Layer", layer)]);
}
export function viaSection(diameter, drill, layers, tented, f) {
  return isection("Via", [irow("Diameter", diameter != null ? f.len(diameter) : null), irow("Drill", drill != null ? `Ø ${f.len(drill)}` : null),
    irow("Layers", layers.join(", ")), irow("Mask", tented)]);
}
export function zoneSection(label, layer, area, unfilled, f) {   // area in mm²
  return isection("Zone", [irow("Name", label), irow("Layer", layer), unfilled ? irow("Fill", "not filled in the file") : null,
    area != null ? irow("Filled area", f.area(area)) : null]);
}
export function netSection(name, info, layers, f) {   // info: {pads, length in mm}
  return isection("Net", [irow("Name", name), info ? irow("Pads", info.pads) : null, info ? irow("Routed length", f.len(info.length)) : null,
    layers && layers.length ? irow("Layers", layers.join(", ")) : null]);
}
export function partSection(c, variant, params, f) {   // a part of a board scene; params: [name, value] already in the page unit
  const b = c.bbox;
  return isection("Part", [irow("Reference", c.ref), irow("Value", c.value), irow("Footprint", c.footprint), irow("Side", c.side),
    c.x != null && c.y != null ? irow("Position", f.xy(c.x, c.y)) : null, c.rotation != null ? irow("Rotation", `${c.rotation}°`) : null,
    b ? irow("Extent", f.pair(b[2] - b[0], b[3] - b[1])) : null, variant ? irow(`Variant ${variant[0]}`, variant[1]) : null,
    ...params.map(([k, v]) => irow(k, v, /^https?:\/\//i.test(String(v)) ? { link: String(v) } : undefined))]);
}
export function keepoutSection(label, layer) {   // "keep-out NAME: what it forbids" or "rule area NAME"
  const m = /^(keep-out|rule area) (.*?)(?:: (.*))?$/.exec(String(label));
  return isection("Keep-out", [irow("Name", m ? m[2] : label), irow("Forbids", m && m[3] ? m[3] : null), irow("Layer", layer)]);
}
export function findingSection(x, layer) {   // a finding of `--check` or of a run
  return isection("Finding", [irow("Code", x.code), irow("Severity", x.severity), irow("Stage", x.stage), irow("Evidence", x.evidence),
    irow("Message", x.message), irow("Where", x.where), irow("Layer", layer), irow("Guidance", x.hint), x.at ? null : irow("Position", "none on this document")]);
}
export function areaOf(ring) {   // the area of a flat ring [x0, y0, x1, y1, …] by the shoelace formula
  let s = 0; for (let i = 0, j = ring.length - 2; i < ring.length; j = i, i += 2) s += (ring[j] + ring[i]) * (ring[j + 1] - ring[i + 1]); return Math.abs(s) / 2;
}
// ---- end inspector model

export const FMT = { len: v => fmtLen(v), nm: v => fmtNm(v), pair: (a, b) => fmtPair(a, b), xy: (a, b) => fmtXY(a, b), area: mm2 => fmtArea(mm2) };
export function fmtArea(mm2) { return UNIT === "mil" ? `${(mm2 / (MIL_MM * MIL_MM)).toFixed(0)} mil²` : `${mm2.toFixed(3)} mm²`; }
export function partParams(c) {   // c0187: every parameter the file holds; an Altium length in the page's unit
  const vs = variantOf(c.ref), params = { ...(c.params || {}), ...((vs && vs.params) || {}) };
  return Object.entries(params).map(([k, v]) => { const mil = /^(-?\d+(?:\.\d+)?)mil$/.exec(String(v)); return [k, mil ? fmtLen(+mil[1] * MIL_MM) : String(v)]; });
}
export function boardPart(ci) { const c = S.comps[ci], vs = variantOf(c.ref); return partSection(c, vs ? [VARIANT, vs.kind] : null, partParams(c), FMT); }
export function netLayers(ni) { const ids = new Set(); for (const pr of S.prims) if (pr[3] === ni && !pr[0].startsWith("View.")) ids.add(pr[0]); return [...ids].map(layerName); }
export function boardNet(ni) { const info = (S.netinfo || [])[ni]; return netSection(S.nets[ni], info ? { pads: info.pads, length: info.length * MM } : null, netLayers(ni), FMT); }
export function boardModel(h, at) {   // a primitive of a board scene, hit at the point `at`
  const pr = h.pr, net = pr[3], ci = pr[4], label = pr[5] || "", lname = h.layer.name, sections = [];
  const pad = label && at ? padOf(label, at[0], at[1]) : null;
  let kind = "item", title = label || lname;
  if (pad) { kind = "pad"; title = `${ci >= 0 ? S.comps[ci].ref : ""} · pad ${pad.number}`; sections.push(padSection(pad, FMT, layerName)); }
  else if (pr[1] === "s") { kind = "track"; title = label || "Track"; sections.push(trackSection(pr[2], lname, FMT)); }
  else if (pr[1] === "a") { kind = "arc"; title = label || "Arc"; sections.push(arcSection(pr[2], pr[6], lname, FMT)); }
  else if (pr[1] === "c" && /^via \d+/.test(label)) {
    kind = "via"; const base = label.replace(/ hole$/, ""), same = S.prims.filter(q => q[5] === base && q[1] === "c");
    const hole = S.prims.find(q => q[5] === base + " hole"), copper = same.filter(q => !/Mask$/.test(q[0]));
    const open = same.filter(q => /Mask$/.test(q[0])).map(q => layerName(q[0]));
    sections.push(viaSection(copper.length ? 2 * copper[0][2][2] : null, hole ? 2 * hole[2][2] : null, copper.map(q => layerName(q[0])),
      open.length ? `open on ${open.join(", ")}` : "tented or not stated", FMT));
    title = base.replace(/^via/, "Via");
  }
  else if (pr[1] === "c" && h.layer.id === "View.Drill") { kind = "hole"; sections.push(isection("Hole", [irow("Diameter", `Ø ${fmtLen(2 * pr[2][2])}`), irow("Centre", FMT.xy(pr[2][0], pr[2][1]))])); }
  else if (pr[1] === "c") sections.push(isection("Circle", [irow("Diameter", fmtLen(2 * pr[2][2])), irow("Layer", lname)]));
  else if (pr[1] === "h" && /^(keep-out|rule area) /.test(label)) { kind = "keepout"; title = "Keep-out"; sections.push(keepoutSection(label, lname)); }
  else if ((pr[1] === "p" || pr[1] === "o") && ci < 0 && net >= 0 || /\((no fill|outline)\)$/.test(label)) {
    kind = "zone"; const name = label.replace(/ \((no fill|outline)\)$/, "");
    sections.push(zoneSection(name, lname, pr[1] === "p" ? pr[2].reduce((s, r) => s + areaOf(r), 0) : null, / \(no fill\)$/.test(label), FMT));
    title = name;
  }
  else sections.push(isection("Item", [irow("Name", label), irow("Layer", lname)]));
  if (kind !== "pad" && kind !== "zone" && kind !== "keepout" && kind !== "via" && sections[0] && !sections[0].rows.some(r => r.label === "Layer"))
    sections[0].rows.push(irow("Layer", lname));
  if (net >= 0) sections.push(boardNet(net), boardRole(net));   // c0273: the net's role after its Net section
  if (ci >= 0) sections.push(boardPart(ci));
  return imodel(kind, title, sections, { subtitle: lname, target: { pr, comp: ci, net, layer: h.layer.id } });
}
export function partModel(ci) { const c = S.comps[ci]; return imodel("part", c.ref, [boardPart(ci)], { subtitle: [c.value, c.footprint].filter(Boolean).join(" · "), target: { comp: ci, net: -1 } }); }
export function netModel(ni) { return imodel("net", S.nets[ni], [boardNet(ni), boardRole(ni)], { subtitle: "Net", target: { comp: -1, net: ni } }); }
export function noteModel(title, text, extra?) { return imodel("note", title, [], { note: text, ...(extra || {}) }); }
