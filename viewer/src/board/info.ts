// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { esc, linkify, showInfo } from "../core/dom";
import { S, st } from "../core/state";
import { fmtLen, fmtNm, fmtPair, MIL_MM } from "../core/units";
import { shareNet } from "../sch/project-nets";
import { draw } from "./draw";
import { VARIANT, variantOf } from "./variants";
import { boardModel, FMT, padSection, partModel } from "../inspect/model";
import { inspect } from "../panels/inspector";
export function compInfo(ci) { return partModel(ci); }   // c0244: the inspector model of a part
export function padOf(label, x, y) {   // the pad entry of a primitive's label nearest the point
  let best = null, bd = Infinity; for (const p of S.pads || []) { if (p.label !== label.replace(/ (hole|slot)$/, "")) continue; const d = Math.hypot(p.x - x, p.y - y); if (d < bd) { bd = d; best = p; } } return best; }
export function layerName(id) { const l = S.layers.find(x => x.id === id); return l ? l.name : id; }
export function padInfo(p) { return padSection(p, FMT, layerName); }   // c0244: the Pad section of the inspector (c0181: an Altium pad's mask and paste)
export function select(h, at?) {
  st.selFinding = -1; st.selNet = -1; st.selComp = -1; st.lastHit = h; st.lastAt = at;
  if (!h) { showInfo(null); draw(); return; }
  const pr = h.pr, net = pr[3], ci = pr[4];
  if (net >= 0) { st.selNet = net; shareNet(S.nets[net]); }
  if (ci >= 0 && net < 0) st.selComp = ci;
  inspect(() => boardModel(h, at)); draw();
}
