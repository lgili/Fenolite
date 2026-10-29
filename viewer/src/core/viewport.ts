// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { draw } from "../board/draw";
import { S, ctx, cv, st, view } from "./state";
import { resize3D } from "../three/view3d";
import { $ } from "./dom";
// ================================================================== 2D view
export let W = 0, H = 0, dpr = 1;
export function setDpr(v) { dpr = v; }
export function measure() { const r = cv.getBoundingClientRect(); dpr = window.devicePixelRatio || 1; W = r.width || W; H = r.height || H;
  cv.width = Math.max(1, Math.round(W * dpr)); cv.height = Math.max(1, Math.round(H * dpr)); }
export let fitted = false;
export function setFitted(v) { fitted = v; }
export function resize() { measure(); if (st.mode3d) resize3D(); if (S && !fitted) fit(); else draw(); }
new ResizeObserver(resize).observe($("wrap"));
export function m() { return view.mirror ? -1 : 1; }
export function w2s(x, y) { return [W / 2 + m() * (x - view.cx) * view.s, H / 2 + (y - view.cy) * view.s]; }
export function s2w(X, Y) { return [view.cx + m() * (X - W / 2) / view.s, view.cy + (Y - H / 2) / view.s]; }
export function worldTf(g?) { (g || ctx).setTransform(dpr * m() * view.s, 0, 0, dpr * view.s, dpr * (W / 2 - m() * view.cx * view.s), dpr * (H / 2 - view.cy * view.s)); }
export function fit(b?) { if (!S || S.kind === "table") return; measure();   // a table (c0190) has no bounds
  b = b || S.bounds; const w = b[2] - b[0], h = b[3] - b[1];
  view.cx = (b[0] + b[2]) / 2; view.cy = (b[1] + b[3]) / 2;
  view.s = Math.max(0.2, Math.min(Math.max(W - 40, 60) / Math.max(w, 1), Math.max(H - 40, 60) / Math.max(h, 1)));
  fitted = W > 100 && H > 100; draw(); }
