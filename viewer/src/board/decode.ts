// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// <decodeV1> c0182: a compact board scene (fenolite.view_scene.v1, view/compact.py) back to its v0 primitives
export function decodeV1(sc) {
  const p = sc.p1; if (!p) return sc;
  const D = p.D, FIXED = { c: 1, s: 2, a: 3 }, last = new Map(), prims = new Array(p.K.length);
  let at = 0, cx = 0, cy = 0;
  const pts = (n, x, y) => { const out = new Array(2 * n); for (let i = 0; i < n; i++) { x += D[at++]; y += D[at++]; out[2 * i] = x; out[2 * i + 1] = y; } return out; };
  for (let k = 0; k < p.K.length; k++) {
    const kind = p.K[k]; let v;
    if (kind === "p" || kind === "o" || kind === "h") { const count = D[at++]; v = []; let rx = cx, ry = cy;
      for (let r = 0; r < count; r++) { const ring = pts(D[at++], rx, ry); if (ring.length) { rx = ring[0]; ry = ring[1]; if (r === 0) { cx = rx; cy = ry; } } v.push(ring); } }
    else if (kind === "l") { const n = D[at++], w = D[at++]; const f = pts(n, cx, cy); cx = f[0]; cy = f[1]; v = [w, ...f]; }
    else { const f = pts(FIXED[kind], cx, cy); cx = f[0]; cy = f[1]; f.push(D[at++]); v = f; }
    const s = p.S[k], n = (last.get(s) || 0) + p.SN[k]; last.set(s, n); const t = p.strings[s];
    prims[k] = [p.layers[p.L[k]], kind, v, p.N[k], p.C[k], t.includes("\u0001") ? t.replace("\u0001", String(n)) : t];
  }
  delete sc.p1; sc.prims = prims; sc.schema = "fenolite.view_scene.v0"; return sc;
}
// </decodeV1>
