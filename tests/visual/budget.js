// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The frame-budget measurement of the viewer page (change c0245, decision 7); run in the page by the harness.
// - open: performance.now() when the harness sees the scene loaded (an upper bound of the first full draw);
// - full: 120 frames of the page's own draw() after a pan or a zoom, each flushed by a one-pixel read;
// - frame: 120 pan and zoom events as a mouse gives them (drag moves and wheel turns), each flushed;
// - cursor: 200 mouse moves; board paints are counted through paintCache;
// - message: a click on a Messages row until the view frames its finding.
const opened = performance.now();
const flush = () => { cv.getContext("2d").getImageData(0, 0, 1, 1); };
const p95 = xs => { const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.ceil(0.95 * s.length) - 1)]; };
const median = xs => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
const rest = () => new Promise(ok => setTimeout(ok, 200));
fit(); flush();
const full = [];
for (let i = 0; i < 120; i++) {
  if (i % 2) view.cx += (i % 4 === 1 ? 3 : -3); else view.s *= (i % 4 === 0 ? 1.1 : 1 / 1.1);
  const t0 = performance.now(); draw(); flush(); full.push(performance.now() - t0);
}
fit(); flush(); await rest();
let painted = 0; const paint0 = paintCache;
paintCache = function () { painted++; return paint0.apply(this, arguments); };
const r = cv.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2, frames = [];
cv.dispatchEvent(new MouseEvent("mousedown", { clientX: cx, clientY: cy, bubbles: true }));
for (let i = 0; i < 120; i++) {
  const e = i % 2
    ? new MouseEvent("mousemove", { clientX: cx + (i % 8) * 6, clientY: cy + (i % 6) * 4, bubbles: true })
    : new WheelEvent("wheel", { clientX: cx, clientY: cy, deltaY: i % 4 === 0 ? -100 : 100, bubbles: true, cancelable: true });
  const t0 = performance.now(); cv.dispatchEvent(e); flush(); frames.push(performance.now() - t0);
}
window.dispatchEvent(new MouseEvent("mouseup", { clientX: cx + 40, clientY: cy, bubbles: true }));
const interactivePaints = painted; painted = 0;
const moves = [];
for (let i = 0; i < 200; i++) {
  const e = new MouseEvent("mousemove", { clientX: r.left + 20 + (i * 7) % (r.width - 40), clientY: r.top + 20 + (i * 11) % (r.height - 40), bubbles: true });
  const t0 = performance.now(); cv.dispatchEvent(e); flush(); moves.push(performance.now() - t0);
}
const cursorPaints = painted;
paintCache = paint0;
await rest();
let message = null;
if (typeof buildMessages === "function" && document.getElementById("msgBody")) {
  const p = S.pads[Math.floor(S.pads.length / 2)];
  S.check = { findings: [{ code: "budget.test", severity: "warning", message: "a finding", where: p.label, stage: "budget", evidence: "INFERRED", layer: p.layers[0], at: [p.x, p.y], box: null }],
    counts: { error: 0, warning: 1, info: 0 }, notes: [], explain: {} };
  buildMessages(); fit(); flush(); await rest();
  const row = document.querySelector("#msgBody tr[data-key]");
  const t0 = performance.now(); row.click(); flush(); message = performance.now() - t0;
}
return { open_ms: opened, full_p95_ms: p95(full), full_median_ms: median(full), frame_p95_ms: p95(frames), frame_median_ms: median(frames),
  interactive_board_paints: interactivePaints, cursor_p95_ms: p95(moves), cursor_median_ms: median(moves), board_paints_during_moves: cursorPaints,
  message_ms: message, prims: S.prims.length, width: r.width, height: r.height };
