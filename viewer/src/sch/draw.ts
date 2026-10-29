// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
import { drawSchDiff } from "../board/diff";
import { draw } from "../board/draw";
import { drawVariantMarks } from "../board/variants";
import { $ } from "../core/dom";
import { textPolylines } from "../core/font";
import { linkLater } from "../core/links";
import { ctx, cv, S, view } from "../core/state";
import { dpr, H, s2w, W, w2s, worldTf } from "../core/viewport";
import { drawMeasure } from "../measure/measure";
import { drawMarks } from "../panels/marks";
import { drawCheck } from "../review/check";
import { MIL, SCH, SEL, WORKSPACE } from "./scene";
export function fontCss(fo, px) { return `${fo.italic ? "italic " : ""}${fo.bold ? "bold " : ""}${px.toFixed(2)}px "${fo.name}", "Times New Roman", Times, serif`; }
export function schAlpha(p) {
  if (SCH.selNet < 0) return 1;
  const o = p.o >= 0 ? S.objects[p.o] : null;
  return o && o.net === SCH.selNet ? 1 : 0.22;
}
export function dashOf(d, w) { const u = Math.max(w, 0.1); return d === 1 ? [u * 4, u * 3] : d === 2 ? [u, u * 2] : d === 3 ? [u * 4, u * 2, u, u * 2] : []; }
export function lineShape(g, x, y, fx, fy, shape, size, color, w) {   // a line end: arrow, solid arrow, tail, solid tail, circle, square
  const L = [0.5, 1, 1.6, 2.4][size || 0] || 1, a = Math.atan2(y - fy, x - fx), c = Math.cos(a), s = Math.sin(a);
  const P = (u, v) => [x + u * c - v * s, y + u * s + v * c];
  g.beginPath();
  if (shape === 1 || shape === 2) { const [ax, ay] = P(-L, -L / 2), [bx, by] = P(-L, L / 2); g.moveTo(ax, ay); g.lineTo(x, y); g.lineTo(bx, by); if (shape === 2) { g.closePath(); g.fillStyle = color; g.fill(); } g.stroke(); }
  else if (shape === 3 || shape === 4) { const [ax, ay] = P(L, -L / 2), [bx, by] = P(L, L / 2); g.moveTo(ax, ay); g.lineTo(x, y); g.lineTo(bx, by); if (shape === 4) { g.closePath(); g.fillStyle = color; g.fill(); } g.stroke(); }
  else if (shape === 5) { g.arc(x, y, L / 2, 0, 2 * Math.PI); g.fillStyle = color; g.fill(); }
  else if (shape === 6) { g.fillStyle = color; g.fillRect(x - L / 2, y - L / 2, L, L); }
}
export function roundRectPath(g, b, rx, ry) {
  const [x0, y0, x1, y1] = b; rx = Math.min(rx, (x1 - x0) / 2); ry = Math.min(ry, (y1 - y0) / 2);
  g.beginPath(); g.moveTo(x0 + rx, y0); g.lineTo(x1 - rx, y0); g.ellipse(x1 - rx, y0 + ry, rx, ry, 0, -Math.PI / 2, 0); g.lineTo(x1, y1 - ry);
  g.ellipse(x1 - rx, y1 - ry, rx, ry, 0, 0, Math.PI / 2); g.lineTo(x0 + rx, y1); g.ellipse(x0 + rx, y1 - ry, rx, ry, 0, Math.PI / 2, Math.PI);
  g.lineTo(x0, y0 + ry); g.ellipse(x0 + rx, y0 + ry, rx, ry, 0, Math.PI, 1.5 * Math.PI); g.closePath();
}
export function strokeW(w) { return Math.max(w, 1 / view.s); }
export function drawStrokeText(p, alpha) {   // KiCad's way: texts as strokes, in Fenolite's own stroke font
  if (p.sz * view.s < 1.5) return;
  const lines = p.s.split("\n"), adv = 1.5 * p.gw, step = p.sz * 1.4, deg = (p.rot || 0) * 90, a = deg * Math.PI / 180;
  ctx.globalAlpha = alpha; ctx.strokeStyle = p.c; ctx.lineWidth = Math.max(p.th, 1 / view.s); ctx.lineCap = "round"; ctx.lineJoin = "round";
  const n = lines.length, first = p.v === "top" ? 0 : p.v === "bottom" ? -(n - 1) : -(n - 1) / 2;
  let wMax = 0; ctx.beginPath();
  lines.forEach((ln, i) => { const off = (first + i) * step, x = p.x + Math.sin(a) * off, y = p.y + Math.cos(a) * off;
    const t = ["", x, y, p.sz, p.gw, p.th, deg, p.h, p.v, false, ln, -1];
    for (const pl of textPolylines(t)) { ctx.moveTo(pl[0][0], pl[0][1]); for (let k = 1; k < pl.length; k++) ctx.lineTo(pl[k][0], pl[k][1]); if (pl.length === 1) ctx.lineTo(pl[0][0] + 1e-4, pl[0][1]); }
    const wl = [...ln].length * adv - 2 * p.gw / 4; wMax = Math.max(wMax, wl);
    if (p.ol && p.ol.length && n === 1) { const x0 = p.h === "left" ? 0 : p.h === "right" ? -wl : -wl / 2, top = p.v === "top" ? 0 : p.v === "bottom" ? -p.sz : -p.sz / 2;
      const ly = top - p.sz * 0.2, c = Math.cos(a), s2 = Math.sin(a), P = lx => [x + lx * c + ly * s2, y - lx * s2 + ly * c];
      for (const k of p.ol) { const [ax, ay] = P(x0 + k * adv), [bx, by] = P(x0 + k * adv + p.gw); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); } } });
  ctx.stroke(); p.sb = [wMax, n * step];
}
export function drawText(p, alpha) {
  if (S.sheet.text === "stroke") return drawStrokeText(p, alpha);
  const fo = S.fonts[p.font] || S.fonts[0], px = fo.emm * view.s; if (px < 1.2) return;
  const [X, Y] = w2s(p.x, p.y);
  ctx.save(); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.globalAlpha = alpha; ctx.translate(X, Y); if (p.rot) ctx.rotate(-p.rot * Math.PI / 2);
  ctx.font = fontCss(fo, px); ctx.fillStyle = p.c; ctx.textAlign = p.h; ctx.textBaseline = p.v === "center" ? "middle" : p.v === "top" ? "top" : "bottom";
  ctx.fillText(p.s, 0, 0);
  const wAll = ctx.measureText(p.s).width, x0 = p.h === "left" ? 0 : p.h === "right" ? -wAll : -wAll / 2;
  const top = p.v === "top" ? 0 : p.v === "center" ? -px / 2 : -px, lw = Math.max(1, px / 14);
  p.sb = [wAll / view.s, px / view.s];   // measured size, for the hit test
  if (p.ol && p.ol.length) { ctx.strokeStyle = p.c; ctx.lineWidth = lw; ctx.beginPath();
    for (const i of p.ol) { const a = ctx.measureText(p.s.slice(0, i)).width, b = ctx.measureText(p.s.slice(0, i + 1)).width; ctx.moveTo(x0 + a, top + lw); ctx.lineTo(x0 + b, top + lw); } ctx.stroke(); }
  if (fo.underline) { ctx.strokeStyle = p.c; ctx.lineWidth = lw; ctx.beginPath(); ctx.moveTo(x0, top + px); ctx.lineTo(x0 + wAll, top + px); ctx.stroke(); }
  ctx.restore();
}
export function wrapLines(g, text, width, wrap) {
  const out = []; for (const para of text.split("\n")) { if (!wrap) { out.push(para); continue; } let line = "";
    for (const word of para.split(/(\s+)/)) { const t = line + word; if (line && g.measureText(t).width > width) { out.push(line.trimEnd()); line = word.trimStart(); } else line = t; } out.push(line); }
  return out;
}
export function drawFrame(p, alpha) {
  const [x0, y0, x1, y1] = p.b; ctx.globalAlpha = alpha;
  if (p.f) { ctx.fillStyle = p.f; ctx.fillRect(x0, y0, x1 - x0, y1 - y0); }
  if (p.bc) { ctx.strokeStyle = p.bc; ctx.lineWidth = strokeW(0.1); ctx.strokeRect(x0, y0, x1 - x0, y1 - y0); }
  const fo = S.fonts[p.font] || S.fonts[0], px = fo.emm * view.s; if (px < 1.2) return;
  const [X0, Y0] = w2s(x0, y0), [X1, Y1] = w2s(x1, y1), m = (p.m || 0) * view.s;
  ctx.save(); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.globalAlpha = alpha; ctx.beginPath(); ctx.rect(X0, Y0, X1 - X0, Y1 - Y0); ctx.clip();
  ctx.font = fontCss(fo, px); ctx.fillStyle = p.tc; ctx.textBaseline = "top";
  const lines = wrapLines(ctx, p.s, X1 - X0 - 2 * m, p.wrap), al = p.al === 1 ? "left" : p.al === 2 ? "right" : p.al === 0 ? "center" : "left";
  ctx.textAlign = al; const x = al === "left" ? X0 + m : al === "right" ? X1 - m : (X0 + X1) / 2;
  lines.forEach((ln, i) => ctx.fillText(ln, x, Y0 + m + i * px * 1.15)); ctx.restore();
}
export function drawImage(p, alpha) {
  const [x0, y0, x1, y1] = p.b; ctx.globalAlpha = alpha;
  if (p.src) { let im = SCH.images.get(p.src); if (!im) { im = new Image(); im.onload = () => draw(); im.src = p.src; SCH.images.set(p.src, im); }
    if (im.complete && im.naturalWidth) { ctx.drawImage(im, x0, y0, x1 - x0, y1 - y0); return; } }
  ctx.strokeStyle = "#888"; ctx.lineWidth = strokeW(0.1); ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.moveTo(x1, y0); ctx.lineTo(x0, y1); ctx.stroke();
}
export function drawPrim(p, alpha) {
  const g = ctx; g.globalAlpha = alpha; g.strokeStyle = p.c; g.lineWidth = strokeW(p.w || 0); g.lineCap = "round"; g.lineJoin = "round";
  switch (p.k) {
    case "l": { const q = p.p; g.setLineDash(p.d ? dashOf(p.d, p.w) : []); g.lineCap = p.d ? "butt" : "round"; g.beginPath(); g.moveTo(q[0], q[1]);
      for (let i = 2; i < q.length; i += 2) g.lineTo(q[i], q[i + 1]); if (q.length === 2) g.lineTo(q[0] + 1e-4, q[1]); g.stroke(); g.setLineDash([]);
      if (p.s0 && q.length >= 4) lineShape(g, q[0], q[1], q[2], q[3], p.s0, p.ss, p.c, p.w);
      if (p.s1 && q.length >= 4) { const n = q.length; lineShape(g, q[n - 2], q[n - 1], q[n - 4], q[n - 3], p.s1, p.ss, p.c, p.w); } break; }
    case "g": { const q = p.p; g.beginPath(); g.moveTo(q[0], q[1]); for (let i = 2; i < q.length; i += 2) g.lineTo(q[i], q[i + 1]); g.closePath();
      if (p.f) { g.fillStyle = p.f; g.fill(); } g.stroke(); break; }
    case "r": { const [x0, y0, x1, y1] = p.b; if (p.rr) roundRectPath(g, p.b, p.rr[0], p.rr[1]); else { g.beginPath(); g.rect(x0, y0, x1 - x0, y1 - y0); }
      if (p.f) { g.globalAlpha = alpha * (p.ta ? 0.5 : 1); g.fillStyle = p.f; g.fill(); g.globalAlpha = alpha; } g.stroke(); break; }
    case "e": g.beginPath(); g.ellipse(p.x, p.y, Math.max(p.rx, 1e-4), Math.max(p.ry, 1e-4), 0, 0, 2 * Math.PI); if (p.f) { g.fillStyle = p.f; g.fill(); } if (p.w || !p.f) g.stroke(); break;
    case "a": { let a0 = p.a0, a1 = p.a1; const full = Math.abs(a1 - a0) >= 360 || a0 === a1; g.beginPath();
      if (p.pie && !full) g.moveTo(p.x, p.y);
      g.ellipse(p.x, p.y, Math.max(p.rx, 1e-4), Math.max(p.ry, 1e-4), 0, full ? 0 : -a0 * Math.PI / 180, full ? 2 * Math.PI : -a1 * Math.PI / 180, !full);
      if (p.pie) { g.closePath(); if (p.f) { g.fillStyle = p.f; g.fill(); } } g.stroke(); break; }
    case "b": { const q = p.p; g.beginPath(); g.moveTo(q[0], q[1]); let i = 2;
      for (; i + 5 < q.length; i += 6) g.bezierCurveTo(q[i], q[i + 1], q[i + 2], q[i + 3], q[i + 4], q[i + 5]); for (; i < q.length; i += 2) g.lineTo(q[i], q[i + 1]); g.stroke(); break; }
    case "t": drawText(p, alpha); break;
    case "x": drawFrame(p, alpha); break;
    case "i": drawImage(p, alpha); break;
  }
}
export function visibleBox() { const [ax, ay] = s2w(0, 0), [bx, by] = s2w(W, H); return [Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by)]; }
export function drawGrid(sh) {
  if (!sh.grid || sh.grid * view.s < 8) return;
  const vb = visibleBox(), g = sh.grid, ox = sh.origin ? sh.origin[0] : 0, oy = sh.origin ? sh.origin[1] : 0, X0 = sh.x0 || 0, Y0 = sh.y0 || 0, X1 = X0 + sh.w, Y1 = Y0 + sh.h;
  const x0 = ox + Math.ceil((Math.max(X0, vb[0]) - ox) / g) * g, x1 = Math.min(X1, vb[2]), y0 = oy + Math.ceil((Math.max(Y0, vb[1]) - oy) / g) * g, y1 = Math.min(Y1, vb[3]);
  if (sh.text === "stroke") {   // KiCad draws its grid as dots
    ctx.globalAlpha = 1; ctx.fillStyle = sh.grid_color || shade(sh.color, 0.3); const d = 1.4 / view.s;
    for (let x = x0; x <= x1; x += g) for (let y = y0; y <= y1; y += g) ctx.fillRect(x - d / 2, y - d / 2, d, d); return; }
  ctx.globalAlpha = 1; ctx.strokeStyle = shade(sh.color, 0.08); ctx.lineWidth = 1 / view.s; ctx.beginPath();
  for (let x = x0; x <= x1; x += g) { ctx.moveTo(x, Math.max(Y0, vb[1])); ctx.lineTo(x, Math.min(Y1, vb[3])); }
  for (let y = y0; y <= y1; y += g) { ctx.moveTo(Math.max(X0, vb[0]), y); ctx.lineTo(Math.min(X1, vb[2]), y); }
  ctx.stroke();
}
export function shade(hex, f) { const n = parseInt(hex.slice(1), 16); const c = [n >> 16, (n >> 8) & 255, n & 255].map(v => Math.round(v * (1 - f))); return `rgb(${c[0]},${c[1]},${c[2]})`; }
export function drawSch() {
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = S.sheet.workspace || WORKSPACE; ctx.fillRect(0, 0, cv.width, cv.height);
  worldTf(); const sh = S.sheet;
  ctx.save(); ctx.shadowColor = "#0008"; ctx.shadowBlur = 12; ctx.shadowOffsetX = 3; ctx.shadowOffsetY = 3; ctx.fillStyle = sh.color; ctx.fillRect(sh.x0 || 0, sh.y0 || 0, sh.w, sh.h); ctx.restore();
  drawGrid(sh);
  const vb = visibleBox(), pad = 2;
  for (const p of S.prims) { const b = p.bb; if (b && (b[2] < vb[0] - pad || b[0] > vb[2] + pad || b[3] < vb[1] - pad || b[1] > vb[3] + pad)) continue; drawPrim(p, schAlpha(p)); }
  ctx.globalAlpha = 1;
  const sb = SCH.selComp >= 0 ? S.comps[SCH.selComp].b : SCH.sel >= 0 && SCH.selNet < 0 ? S.objects[SCH.sel].b : null;
  if (sb) { const e = 4 / view.s; ctx.strokeStyle = SEL; ctx.lineWidth = 1.5 / view.s; ctx.setLineDash([5 / view.s, 3 / view.s]); ctx.strokeRect(sb[0] - e, sb[1] - e, sb[2] - sb[0] + 2 * e, sb[3] - sb[1] + 2 * e); ctx.setLineDash([]); }
  drawSchDiff(); drawCheck(); drawMarks(); linkLater(); if (S.variants) drawVariantMarks(S.comps.map(c => [c.group || c.ref, c.b])); drawMeasure();
  $("zoomv").textContent = `zoom ${(view.s * MIL * 100).toFixed(0)} %`;
}
