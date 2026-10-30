// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== the view cube (c0301, design decision 6)
// A 96-pixel cube at the top right of the 3D view, turned with the camera: its faces read Top, Bottom, Front,
// Back, Left and Right in Fenolite's stroke font; a click on a face sets that view, a click near a corner the iso
// view from that corner, both animated over 250 ms. A 2D canvas projection of the camera's axes, no WebGL.
import { textPolylines } from "../core/font";
import { $ } from "../core/dom";
import { camBasis, camPreset, V3 } from "./view3d";

export const CUBE_FACES = [   // normal in the 3D frame (x right, y back, z up), its label, the camera preset
  { n: [0, 0, 1], label: "TOP", view: "top" }, { n: [0, 0, -1], label: "BOTTOM", view: "bottom" },
  { n: [0, -1, 0], label: "FRONT", view: "front" }, { n: [0, 1, 0], label: "BACK", view: "back" },
  { n: [-1, 0, 0], label: "LEFT", view: "left" }, { n: [1, 0, 0], label: "RIGHT", view: "right" },
];
const cubeEl = $("cube") as HTMLCanvasElement;
let cubeHits = [], cubeTokens = null, cubeTheme = "";
function tokens() {   // the interface colours of the cube, read again when the theme changes
  const key = document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: light)").matches ? "system-light" : "system-dark");
  if (cubeTokens && key === cubeTheme) return cubeTokens;
  const cs = getComputedStyle(document.documentElement), v = n => cs.getPropertyValue(n).trim();
  cubeTheme = key; cubeTokens = { face: v("--surface-2"), side: v("--surface-3"), edge: v("--border-strong"), text: v("--text-1"), dim: v("--text-3"), accent: v("--accent") };
  return cubeTokens;
}
export function drawCube() {
  if (!cubeEl || cubeEl.style.display === "none") return;
  const dpr = window.devicePixelRatio || 1, size = 112, g = cubeEl.getContext("2d"), T = tokens();
  if (cubeEl.width !== size * dpr) { cubeEl.width = size * dpr; cubeEl.height = size * dpr; }
  g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, size, size);
  const [r, u, b] = camBasis(), s = 30, c = size / 2;
  const P = v => { const x = v[0] * r[0] + v[1] * r[1] + v[2] * r[2], y = v[0] * u[0] + v[1] * u[1] + v[2] * u[2], z = v[0] * b[0] + v[1] * b[1] + v[2] * b[2]; return [c + x * s, c - y * s, z]; };
  const faces = CUBE_FACES.map(f => {
    const n = f.n, axis = n.findIndex(x => x !== 0), o = [0, 1, 2].filter(k => k !== axis);
    const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([p, q]) => { const v = [0, 0, 0]; v[axis] = n[axis]; v[o[0]] = p; v[o[1]] = q; return P(v); });
    const facing = n[0] * b[0] + n[1] * b[1] + n[2] * b[2];
    return { ...f, corners, facing, center: P(n) };
  }).filter(f => f.facing > 0.02).sort((p, q) => p.facing - q.facing);
  cubeHits = [];
  for (const f of faces) {
    g.beginPath(); f.corners.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y)); g.closePath();
    g.globalAlpha = 0.92; g.fillStyle = f.facing > 0.7 ? T.face : T.side; g.fill(); g.globalAlpha = 1;
    g.strokeStyle = T.edge; g.lineWidth = 1; g.stroke();
    const xs = f.corners.map(p => p[0]), ys = f.corners.map(p => p[1]), fw = Math.max(...xs) - Math.min(...xs), fh = Math.max(...ys) - Math.min(...ys);
    const h = Math.min(9, 0.72 * fw / (f.label.length - 0.33), 0.5 * fh);
    if (f.facing > 0.3 && h >= 4.5) {   // the label, in the stroke font, upright on screen, as wide as its face allows
      const lines = textPolylines(["", f.center[0], f.center[1], h, 0, 1, 0, "center", "center", false, f.label]);
      g.strokeStyle = f.facing > 0.7 ? T.text : T.dim; g.lineWidth = 1.2; g.lineCap = "round"; g.lineJoin = "round";
      for (const pl of lines) { g.beginPath(); pl.forEach(([x, y], i) => i ? g.lineTo(x, y) : g.moveTo(x, y)); g.stroke(); }
    }
    cubeHits.push({ kind: "face", view: f.view, poly: f.corners });
  }
  for (const sx of [-1, 1]) for (const sy of [-1, 1]) for (const sz of [-1, 1]) {   // the corners in view: iso views
    const p = P([sx, sy, sz]); if (p[2] < -0.2) continue;
    g.beginPath(); g.arc(p[0], p[1], 2.5, 0, 2 * Math.PI); g.fillStyle = T.accent; g.fill();
    cubeHits.unshift({ kind: "corner", view: [Math.atan2(sy, sx), sz * 0.6155], at: p });
  }
}
function inPoly(x, y, poly) { let inside = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
  const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside; } return inside; }
export function cubeAt(x, y) {   // what a click at (x, y) of the cube's canvas means: a corner first, then the nearest face drawn on top
  for (const h of cubeHits) if (h.kind === "corner" && Math.hypot(h.at[0] - x, h.at[1] - y) <= 7) return h;
  for (let i = cubeHits.length - 1; i >= 0; i--) { const h = cubeHits[i]; if (h.kind === "face" && inPoly(x, y, h.poly)) return h; }
  return null;
}
cubeEl.addEventListener("click", e => { const h = cubeAt(e.offsetX, e.offsetY); if (h) camPreset(h.view, true); });
cubeEl.addEventListener("mousemove", e => { cubeEl.style.cursor = cubeAt(e.offsetX, e.offsetY) ? "pointer" : "default"; });
export const cubeFrame = () => V3.cam;
