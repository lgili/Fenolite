// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ---- SVG: the view drawn again into a recorder of the canvas calls the page makes, as vector paths
import { buildCaches } from "../board/cache";
import { draw } from "../board/draw";
import { $, download, esc, showInfo } from "../core/dom";
import { ctx, DOC, P2D, S, setCtx, setP2D, st, view } from "../core/state";
import { dpr, H, setDpr, W } from "../core/viewport";
import { isSch } from "../sch/scene";
export class RecPath {   // what a Path2D records, replayed under the transform of the fill or stroke
  declare c: any[];
  constructor() { this.c = []; }
  moveTo(x, y) { this.c.push(["M", x, y]); } lineTo(x, y) { this.c.push(["L", x, y]); } closePath() { this.c.push(["Z"]); }
  rect(x, y, w, h) { this.c.push(["M", x, y], ["L", x + w, y], ["L", x + w, y + h], ["L", x, y + h], ["Z"]); }
  arc(cx, cy, r, a0, a1, ccw) { this.ellipse(cx, cy, r, r, 0, a0, a1, ccw); }
  ellipse(cx, cy, rx, ry, rot, a0, a1, ccw) { const T = 2 * Math.PI; let span = ccw ? a0 - a1 : a1 - a0; if (Math.abs(span) >= T) span = T; else span = ((span % T) + T) % T;
    const n = Math.max(8, Math.ceil(span / (Math.PI / 32))), cr = Math.cos(rot), sr = Math.sin(rot);
    for (let i = 0; i <= n; i++) { const t = a0 + (ccw ? -1 : 1) * span * i / n, ex = rx * Math.cos(t), ey = ry * Math.sin(t);
      this.c.push([i === 0 && !this.c.length ? "M" : "L", cx + ex * cr - ey * sr, cy + ex * sr + ey * cr]); } }
  bezierCurveTo(a, b, c, d, x, y) { this.c.push(["C", a, b, c, d, x, y]); }
}
export const SVG_NS = ["http:", "", "www.w3.org", "2000", "svg"].join("/");   // the SVG namespace: a name, never fetched (the page loads nothing)
export class SvgCtx {
  declare out: string[]; declare defs: string[]; declare k: number; declare st: any; declare stack: any[]; declare path: any; declare canvas: any; declare meas: any;
  constructor(w, h) { this.out = []; this.defs = []; this.k = 0; this.st = { m: [1, 0, 0, 1, 0, 0], fillStyle: "#000", strokeStyle: "#000", lineWidth: 1, lineCap: "butt", lineJoin: "miter", globalAlpha: 1, dash: [], font: "10px sans-serif", textAlign: "start", textBaseline: "alphabetic", clip: null };
    this.stack = []; this.path = new RecPath(); this.canvas = { width: w, height: h }; this.meas = document.createElement("canvas").getContext("2d"); }
  get fillStyle() { return this.st.fillStyle; } set fillStyle(v) { this.st.fillStyle = v; }
  get strokeStyle() { return this.st.strokeStyle; } set strokeStyle(v) { this.st.strokeStyle = v; }
  get lineWidth() { return this.st.lineWidth; } set lineWidth(v) { this.st.lineWidth = v; }
  get lineCap() { return this.st.lineCap; } set lineCap(v) { this.st.lineCap = v; }
  get lineJoin() { return this.st.lineJoin; } set lineJoin(v) { this.st.lineJoin = v; }
  get globalAlpha() { return this.st.globalAlpha; } set globalAlpha(v) { this.st.globalAlpha = v; }
  get font() { return this.st.font; } set font(v) { this.st.font = v; }
  get textAlign() { return this.st.textAlign; } set textAlign(v) { this.st.textAlign = v; }
  get textBaseline() { return this.st.textBaseline; } set textBaseline(v) { this.st.textBaseline = v; }
  set shadowColor(v) { } set shadowBlur(v) { } set shadowOffsetX(v) { } set shadowOffsetY(v) { }
  save() { this.stack.push({ ...this.st, m: [...this.st.m], dash: [...this.st.dash] }); } restore() { if (this.stack.length) this.st = this.stack.pop(); }
  setTransform(a, b, c, d, e, f) { this.st.m = [a, b, c, d, e, f]; }
  transform(a, b, c, d, e, f) { const [A, B, C, D, E, F] = this.st.m; this.st.m = [A * a + C * b, B * a + D * b, A * c + C * d, B * c + D * d, A * e + C * f + E, B * e + D * f + F]; }
  translate(x, y) { this.transform(1, 0, 0, 1, x, y); } scale(x, y) { this.transform(x, 0, 0, y, 0, 0); } rotate(t) { const c = Math.cos(t), s = Math.sin(t); this.transform(c, s, -s, c, 0, 0); }
  setLineDash(d) { this.st.dash = [...d]; } getLineDash() { return [...this.st.dash]; }
  beginPath() { this.path = new RecPath(); }
  moveTo(x, y) { this.path.moveTo(x, y); } lineTo(x, y) { this.path.lineTo(x, y); } closePath() { this.path.closePath(); }
  rect(x, y, w, h) { this.path.rect(x, y, w, h); } arc(...a) { this.path.arc(...a); } ellipse(...a) { this.path.ellipse(...a); } bezierCurveTo(...a) { this.path.bezierCurveTo(...a); }
  measureText(t) { this.meas.font = this.st.font; return this.meas.measureText(t); }
  _scale() { const [a, b, c, d] = this.st.m; return Math.sqrt(Math.abs(a * d - b * c)) || 1; }
  _d(p) { const [a, b, c, d, e, f] = this.st.m, X = (x, y) => (a * x + c * y + e).toFixed(2), Y = (x, y) => (b * x + d * y + f).toFixed(2);
    return p.c.map(o => o[0] === "Z" ? "Z" : o[0] === "C" ? `C${X(o[1], o[2])} ${Y(o[1], o[2])} ${X(o[3], o[4])} ${Y(o[3], o[4])} ${X(o[5], o[6])} ${Y(o[5], o[6])}` : `${o[0]}${X(o[1], o[2])} ${Y(o[1], o[2])}`).join(""); }
  _clip() { return this.st.clip ? ` clip-path="url(#${this.st.clip})"` : ""; }
  _alpha() { return this.st.globalAlpha < 1 ? ` opacity="${this.st.globalAlpha.toFixed(3)}"` : ""; }
  fill(p, rule?) { if (typeof p === "string") { rule = p; p = null; } const d = this._d(p || this.path); if (!d) return;
    this.out.push(`<path d="${d}" fill="${this.st.fillStyle}"${rule === "evenodd" ? ' fill-rule="evenodd"' : ""}${this._alpha()}${this._clip()}/>`); }
  stroke(p) { const d = this._d(p || this.path); if (!d) return; const k = this._scale(), dash = this.st.dash.length ? ` stroke-dasharray="${this.st.dash.map(v => (v * k).toFixed(2)).join(" ")}"` : "";
    this.out.push(`<path d="${d}" fill="none" stroke="${this.st.strokeStyle}" stroke-width="${(this.st.lineWidth * k).toFixed(3)}" stroke-linecap="${this.st.lineCap}" stroke-linejoin="${this.st.lineJoin}"${dash}${this._alpha()}${this._clip()}/>`); }
  fillRect(x, y, w, h) { const p = new RecPath(); p.rect(x, y, w, h); this.fill(p); } strokeRect(x, y, w, h) { const p = new RecPath(); p.rect(x, y, w, h); this.stroke(p); }
  clearRect() { }
  clip(p, rule) { if (typeof p === "string") { rule = p; p = null; } const id = `c${this.k++}`; this.defs.push(`<clipPath id="${id}"><path d="${this._d(p || this.path)}"${rule === "evenodd" ? ' clip-rule="evenodd"' : ""}/></clipPath>`); this.st.clip = id; }
  fillText(t, x, y) { const [a, b, c, d, e, f] = this.st.m, anchor = { center: "middle", right: "end", end: "end" }[this.st.textAlign] || "start";
    const base = { middle: "central", top: "hanging", hanging: "hanging", bottom: "text-after-edge" }[this.st.textBaseline] || "alphabetic";
    this.out.push(`<text transform="matrix(${[a, b, c, d, e, f].map(v => +v.toFixed(5)).join(" ")})" x="${x}" y="${y}" style="font:${esc(this.st.font)}" fill="${this.st.fillStyle}" text-anchor="${anchor}" dominant-baseline="${base}"${this._alpha()}${this._clip()}>${esc(t)}</text>`); }
  drawImage(img, x, y, w, h) { const [a, b, c, d, e, f] = this.st.m; if (!img || !img.src) return;
    this.out.push(`<image href="${esc(img.src)}" x="${x}" y="${y}" width="${w ?? img.width}" height="${h ?? img.height}" transform="matrix(${[a, b, c, d, e, f].join(" ")})" preserveAspectRatio="none"${this._alpha()}${this._clip()}/>`); }
  svg(w, h, size) { return `<svg xmlns="${SVG_NS}" viewBox="0 0 ${w} ${h}" ${size || `width="${w}" height="${h}"`}><title>${esc(DOC ? DOC.name : "view")}</title><defs>${this.defs.join("")}</defs>${this.out.join("\n")}</svg>`; }
}
export function viewSvg(size?) {   // the view as an SVG text; null in 3D
  if (!S || st.mode3d) return null;
  const real = ctx, realDpr = dpr, rec = new SvgCtx(W, H); const board = !isSch();
  setCtx(rec); setDpr(1); if (board) { setP2D(RecPath); buildCaches(); if (S.diff) S.diff.cache = null; }
  try { draw(); } finally { setCtx(real); setDpr(realDpr); if (board) { setP2D(Path2D); buildCaches(); if (S.diff) S.diff.cache = null; } draw(); }
  return rec.svg(W, H, size);
}
$("bSvg").onclick = () => { const svg = viewSvg(); if (!svg) { showInfo("SVG: leave the 3D view first (D)."); return; } download(svg, (DOC ? DOC.name : "view") + ".svg", "image/svg+xml"); };
export function printView() {   // the SVG at the chosen scale, printed from a hidden frame: the print dialog also saves a PDF
  const k = $("printScale").value, size = k === "fit" ? 'width="100%" height="100%" preserveAspectRatio="xMidYMid meet"' : `width="${(W / view.s * +k).toFixed(3)}mm" height="${(H / view.s * +k).toFixed(3)}mm"`;
  const svg = viewSvg(size); if (!svg) { showInfo("Print: leave the 3D view first (D)."); return; }
  const f = document.createElement("iframe"); f.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0"; document.body.appendChild(f);
  const scale = k === "fit" ? "fit to page" : `scale ${k}:1`;
  f.contentDocument.open(); f.contentDocument.write(`<!doctype html><html><head><title>${esc(DOC ? DOC.name : "view")}</title><style>@page { margin: 10mm } html, body { margin: 0; height: 100% } svg { display: block; ${k === "fit" ? "width: 100%; height: 95vh" : ""} } p { font: 9pt system-ui; margin: 2mm 0 0 }</style></head><body>${svg}<p>${esc(DOC ? DOC.name : "")} · ${scale} · Fenolite viewer</p></body></html>`); f.contentDocument.close();
  setTimeout(() => { f.contentWindow.focus(); f.contentWindow.print(); setTimeout(() => f.remove(), 2000); }, 200);
}
$("bPrint").onclick = printView;
