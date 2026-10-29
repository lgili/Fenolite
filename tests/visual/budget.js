// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The frame-budget measurement of the viewer page (change c0245, decision 7); run in the page by the harness.
const opened = performance.now();
const flush = () => { const g = cv.getContext("2d"); g.getImageData(0, 0, 1, 1); };
const p95 = xs => { const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.ceil(0.95 * s.length) - 1)]; };
const median = xs => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
fit(); flush();
const frames = [];
for (let i = 0; i < 120; i++) {
  if (i % 2) view.cx += (i % 4 === 1 ? 3 : -3); else view.s *= (i % 4 === 0 ? 1.1 : 1 / 1.1);
  const t0 = performance.now(); draw(); flush(); frames.push(performance.now() - t0);
}
let painted = 0; const paint0 = paintCache;
paintCache = function () { painted++; return paint0.apply(this, arguments); };
const r = cv.getBoundingClientRect(), moves = [];
for (let i = 0; i < 200; i++) {
  const e = new MouseEvent("mousemove", { clientX: r.left + 20 + (i * 7) % (r.width - 40), clientY: r.top + 20 + (i * 11) % (r.height - 40), bubbles: true });
  const t0 = performance.now(); cv.dispatchEvent(e); flush(); moves.push(performance.now() - t0);
}
paintCache = paint0;
return { open_ms: opened, frame_p95_ms: p95(frames), frame_median_ms: median(frames), cursor_p95_ms: p95(moves),
  cursor_median_ms: median(moves), board_paints_during_moves: painted, prims: S.prims.length, width: r.width, height: r.height };
