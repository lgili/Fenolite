// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== assembly variants of an Altium project (c0186)
import { refreshToolbar } from "../panels/toolbar";
import { ctx, S, st, view } from "../core/state";
import { draw3D, rebuildBodies, V3 } from "../three/view3d";
import { draw } from "./draw";
export let VARIANT = null;
export function variantOf(ref) { const v = VARIANT && S && S.variants && S.variants[VARIANT]; return v ? v[ref] || null : null; }
export function notFitted(ref) { const v = variantOf(ref); return !!(v && v.kind === "not fitted"); }
export function variantNames() { return S && S.variants ? Object.keys(S.variants) : []; }
export function buildVariants() {   // the toolbar's variant selector (c0243) shows the project's variants
  if (S && S.variant && VARIANT === null) VARIANT = S.variant;
  refreshToolbar();
}
export function setVariant(v) { VARIANT = v || null; if (V3.built) { rebuildBodies(); } draw(); if (st.mode3d) draw3D(); }
export function drawVariantMarks(boxes) {   // a cross over every part the variant does not fit, as Altium marks them
  if (!VARIANT) return; ctx.globalAlpha = 1; ctx.strokeStyle = "#ff3030"; ctx.lineWidth = 2 / view.s;
  for (const [ref, b] of boxes) { if (!b || !notFitted(ref)) continue;
    ctx.beginPath(); ctx.moveTo(b[0], b[1]); ctx.lineTo(b[2], b[3]); ctx.moveTo(b[2], b[1]); ctx.lineTo(b[0], b[3]); ctx.stroke(); }
}
