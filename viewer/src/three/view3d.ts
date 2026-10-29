// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== 3D view (WebGL, no library)
import { cache } from "../board/cache";
import { paintCache, paintTexts } from "../board/draw";
import { boardPath, ringSamples } from "../board/geometry";
import { compInfo } from "../board/info";
import { notFitted } from "../board/variants";
import { $, esc, showInfo } from "../core/dom";
import { cv, S, st } from "../core/state";
import { dpr, fitted, H, measure, resize, setFitted, W } from "../core/viewport";
import { refreshDock } from "../panels/dock";
import { refreshToolbar } from "../panels/toolbar";
import { drawCube } from "./view-cube";
import { inv, lookAt, mul, persp } from "./math";
import { boardPart, imodel, irow, isection } from "../inspect/model";
import { inspect } from "../panels/inspector";
import { fmtLen } from "../core/units";
export const glc = $("gl");
export const LIGHT = { ambient: "0.30", key: "0.55", fill: "0.20" };   // c0301: the terms of the 3D lighting (GLSL literals)
export const V3: any = {   // any: init3D and buildMeshes add the model program and buffers
  gl: null, prog: null, loc: {}, parts: [], tex: {}, built: false, cam: { yaw: -2.2, pitch: 0.75, dist: 260, tx: 0, ty: 0, tz: 0 }, selBody: -1, bodies: true, bodyPart: null,
  board: true, silk: true, copper: true, anim: 0 };   // c0301: the 3D panel's toggles
export function shader(gl, type, src) { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; }
export function init3D() {
  if (V3.gl) return true;
  const gl = glc.getContext("webgl", { antialias: true }); if (!gl) { showInfo("This browser has no WebGL: the 3D view is not available."); return false; }
  const vs = `attribute vec3 aP; attribute vec3 aN; attribute vec3 aC; attribute vec2 aT; uniform mat4 uM; varying vec3 vN; varying vec3 vC; varying vec2 vT;
    void main(){ gl_Position = uM * vec4(aP, 1.0); vN = aN; vC = aC; vT = aT; }`;
  const fs = `precision mediump float; varying vec3 vN; varying vec3 vC; varying vec2 vT; uniform sampler2D uS; uniform float uTex; uniform vec3 uL; uniform vec3 uL2;
    void main(){ vec4 t = texture2D(uS, vT); if (uTex > 0.5 && t.a < 0.5) discard; vec3 base = uTex > 0.5 ? t.rgb : vC; vec3 n = normalize(vN);
      gl_FragColor = vec4(base * (${LIGHT.ambient} + ${LIGHT.key} * max(dot(n, uL), 0.0) + ${LIGHT.fill} * abs(dot(n, uL2))), 1.0); }`;
  const p = gl.createProgram(); gl.attachShader(p, shader(gl, gl.VERTEX_SHADER, vs)); gl.attachShader(p, shader(gl, gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
  V3.gl = gl; V3.prog = p; for (const k of ["aP", "aN", "aC", "aT"]) V3.loc[k] = gl.getAttribLocation(p, k);
  for (const k of ["uM", "uS", "uTex", "uL", "uL2"]) V3.loc[k] = gl.getUniformLocation(p, k);
  // body models (change c0193): per-vertex colour, alpha 0 where the model gives none (the body colour then)
  V3.u32 = !!gl.getExtension("OES_element_index_uint");
  const mvs = `attribute vec3 aP; attribute vec3 aN; attribute vec4 aC; uniform mat4 uVP; uniform mat4 uW; varying vec3 vN; varying vec4 vC;
    void main(){ gl_Position = uVP * uW * vec4(aP, 1.0); vN = (uW * vec4(aN, 0.0)).xyz; vC = aC; }`;
  const mfs = `precision mediump float; varying vec3 vN; varying vec4 vC; uniform vec3 uBody; uniform float uSel; uniform vec3 uL; uniform vec3 uL2;
    void main(){ vec3 base = vC.a > 0.5 ? vC.rgb : uBody; if (uSel > 0.5) base = mix(base, vec3(1.0, 0.85, 0.3), 0.55); vec3 n = normalize(vN);
      gl_FragColor = vec4(base * (${LIGHT.ambient} + ${LIGHT.key} * max(dot(n, uL), 0.0) + ${LIGHT.fill} * abs(dot(n, uL2))), 1.0); }`;
  const q = gl.createProgram(); gl.attachShader(q, shader(gl, gl.VERTEX_SHADER, mvs)); gl.attachShader(q, shader(gl, gl.FRAGMENT_SHADER, mfs)); gl.linkProgram(q);
  V3.mprog = q; V3.mloc = {}; for (const k of ["aP", "aN", "aC"]) V3.mloc[k] = gl.getAttribLocation(q, k);
  for (const k of ["uVP", "uW", "uBody", "uSel", "uL", "uL2"]) V3.mloc[k] = gl.getUniformLocation(q, k);
  return true;
}
export function b64(text, Type) { const bin = atob(text), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i); return new Type(u8.buffer); }
export function buildMeshes() {
  const gl = V3.gl; for (const m of Object.values(V3.meshBufs || {})) for (const k of ["pos", "nrm", "col", "idx"]) gl.deleteBuffer(m[k]);
  V3.meshBufs = {};
  for (const [key, ms] of Object.entries<any>(S.meshes || {})) {
    if (!ms) continue;
    const P = b64(ms.v, Float32Array), I = b64(ms.i, Uint32Array), C = b64(ms.c, Uint8Array), N = new Float32Array(P.length);
    for (let t = 0; t < I.length; t += 3) { const a = I[t] * 3, b = I[t + 1] * 3, c = I[t + 2] * 3;
      const ux = P[b] - P[a], uy = P[b + 1] - P[a + 1], uz = P[b + 2] - P[a + 2], vx = P[c] - P[a], vy = P[c + 1] - P[a + 1], vz = P[c + 2] - P[a + 2];
      const nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx; for (const o of [a, b, c]) { N[o] += nx; N[o + 1] += ny; N[o + 2] += nz; } }
    for (let o = 0; o < N.length; o += 3) { const l = Math.hypot(N[o], N[o + 1], N[o + 2]) || 1; N[o] /= l; N[o + 1] /= l; N[o + 2] /= l; }
    const buf = (data, target) => { const b = gl.createBuffer(); gl.bindBuffer(target, b); gl.bufferData(target, data, gl.STATIC_DRAW); return b; };
    let idx = I, type = gl.UNSIGNED_INT;
    if (!V3.u32) { if (P.length / 3 > 65535) continue; idx = new Uint16Array(I); type = gl.UNSIGNED_SHORT; }
    V3.meshBufs[key] = { pos: buf(P, gl.ARRAY_BUFFER), nrm: buf(N, gl.ARRAY_BUFFER), col: buf(C, gl.ARRAY_BUFFER), idx: buf(idx, gl.ELEMENT_ARRAY_BUFFER), n: I.length, type };
  }
}

export function hexRGB(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]; }
export function makePart(data, tex) { const gl = V3.gl, b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
  return { buf: b, n: data.length / 11, tex }; }
export function push(arr, p, n, c, t?) { arr.push(p[0], p[1], p[2], n[0], n[1], n[2], c[0], c[1], c[2], t ? t[0] : 0, t ? t[1] : 0); }
export function quad(arr, a, b, c2, d, col) { const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2], vx = d[0] - a[0], vy = d[1] - a[1], vz = d[2] - a[2];
  const n = [uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx]; for (const p of [a, b, c2, a, c2, d]) push(arr, p, n, col); }
// 3D coordinates: x along the board, y = -board y (so the front face is seen from +z with the board upright), z up
export function P3(x, y, z) { return [x, -y, z]; }
export function sideTexture(side) {
  const b = S.bounds, w = b[2] - b[0], h = b[3] - b[1], maxT = V3.gl.getParameter(V3.gl.MAX_TEXTURE_SIZE);
  const ppm = Math.min(16, (Math.min(maxT, 8192) - 2) / Math.max(w, h)), cw = Math.ceil(w * ppm), ch = Math.ceil(h * ppm);
  const c = document.createElement("canvas"); c.width = cw; c.height = ch; const g = c.getContext("2d");
  g.setTransform(ppm, 0, 0, ppm, -b[0] * ppm, -b[1] * ppm);
  g.fillStyle = "#1d5f33"; g.fill(boardPath(), "evenodd");
  g.save(); g.clip(boardPath(), "evenodd");
  const pre = side === "top" ? "F." : "B.";
  const lay = id => S.layers.find(l => l.id === id);
  if (lay(pre + "Cu") && V3.copper) paintCache(g, cache.get(pre + "Cu"), pre + "Cu", "#2b8a45", 1, ppm);
  if (lay(pre + "Mask")) paintCache(g, cache.get(pre + "Mask"), pre + "Mask", "#d4b05c", 1, ppm);
  if (lay(pre + "SilkS") && V3.silk) { paintCache(g, cache.get(pre + "SilkS"), pre + "SilkS", "#f1f1ea", 1, ppm); paintTexts(g, pre + "SilkS", "#f1f1ea", 1, ppm); }
  if (lay("View.Drill")) paintCache(g, cache.get("View.Drill"), "View.Drill", "#0b0b0b", 1, ppm);
  g.restore();
  const gl = V3.gl, t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  return t;
}
export function bodyGeometry(arr, bd, col) {
  const T = S.board3d.thickness, dn = bd.side === "bottom";
  const zA = dn ? -bd.z0 : T + bd.z0, zB = dn ? -bd.z1 : T + bd.z1, ring = [];
  for (let i = 0; i < bd.ring.length; i += 2) ring.push([bd.ring[i], bd.ring[i + 1]]);
  const n = ring.length; if (n < 3) return;
  for (let i = 0; i < n; i++) { const a = ring[i], b = ring[(i + 1) % n]; quad(arr, P3(a[0], a[1], zA), P3(b[0], b[1], zA), P3(b[0], b[1], zB), P3(a[0], a[1], zB), col); }
  let cx = 0, cy = 0; for (const p of ring) { cx += p[0]; cy += p[1]; } cx /= n; cy /= n;
  const cap = col === BODY_RGB ? hexRGB(BODY_TOP) : col.map(v => v + (1 - v) * 0.18);
  for (let i = 0; i < n; i++) { const a = ring[i], b = ring[(i + 1) % n]; for (const p of [[cx, cy], a, b]) push(arr, P3(p[0], p[1], zB), [0, 0, dn ? -1 : 1], cap); }
}
export function build3D() {
  if (!init3D()) return false;
  const gl = V3.gl; for (const p of V3.parts) gl.deleteBuffer(p.buf); V3.parts = [];
  for (const k of Object.keys(V3.tex)) gl.deleteTexture(V3.tex[k]);
  V3.tex.top = sideTexture("top"); V3.tex.bottom = sideTexture("bottom");
  const b = S.bounds, w = b[2] - b[0], h = b[3] - b[1], T = S.board3d.thickness;
  const top = [], bot = [], edge = [], corners = [[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]]];
  const uv = p => [(p[0] - b[0]) / w, (p[1] - b[1]) / h];
  for (const tri of [[0, 1, 2], [0, 2, 3]]) { for (const k of tri) push(top, P3(corners[k][0], corners[k][1], T), [0, 0, 1], [1, 1, 1], uv(corners[k]));
    for (const k of [tri[0], tri[2], tri[1]]) push(bot, P3(corners[k][0], corners[k][1], 0), [0, 0, -1], [1, 1, 1], uv(corners[k])); }
  const ec = hexRGB("#a99c62");
  for (const r of S.board) { const pts = ringSamples(r); for (let i = 0; i < pts.length; i++) { const a = pts[i], c2 = pts[(i + 1) % pts.length];
    quad(edge, P3(a[0], a[1], 0), P3(c2[0], c2[1], 0), P3(c2[0], c2[1], T), P3(a[0], a[1], T), ec); } }
  V3.parts.push(makePart(top, "top"), makePart(bot, "bottom"), makePart(edge, null));
  V3.bodyPart = null; buildMeshes(); rebuildBodies();
  if (!V3.built) { V3.cam.tx = (b[0] + b[2]) / 2; V3.cam.ty = -(b[1] + b[3]) / 2; V3.cam.tz = 0; V3.cam.dist = Math.max(w, h) * 1.7; }
  V3.built = true; return true;
}
export const BODY = "#33363c", BODY_TOP = "#5b6069", BODY_SEL = "#ffd84d", MESH_BODY = "#9aa0a8";   // c0301: Fenolite's body colours
export const BODY_RGB = hexRGB(BODY);
export function rebuildBodies() {
  const gl = V3.gl; if (!gl) return; if (V3.bodyPart) gl.deleteBuffer(V3.bodyPart.buf);
  const arr = []; (S.bodies || []).forEach((bd, i) => { if (notFitted(bd.ref)) return; if (bd.mesh && V3.meshBufs && V3.meshBufs[bd.mesh]) return;
    const sel = i === V3.selBody || (st.selComp >= 0 && bd.comp === st.selComp);
    bodyGeometry(arr, bd, sel ? hexRGB(BODY_SEL) : BODY_RGB); });
  V3.bodyPart = arr.length ? makePart(arr, null) : null;
}

export function camEye() { const c = V3.cam; return [c.tx + c.dist * Math.cos(c.pitch) * Math.cos(c.yaw), c.ty + c.dist * Math.cos(c.pitch) * Math.sin(c.yaw), c.tz + c.dist * Math.sin(c.pitch)]; }
export function mvp() { const c = V3.cam, e = camEye(), up = Math.abs(Math.cos(c.pitch)) < 1e-3 ? [Math.cos(c.yaw + Math.PI), Math.sin(c.yaw + Math.PI), 0] : [0, 0, 1];
  return mul(persp(0.75, Math.max(W, 1) / Math.max(H, 1), c.dist * 0.01, c.dist * 10), lookAt(e, [c.tx, c.ty, c.tz], up)); }
export function camBasis() {   // the camera's right, up and back axes in the 3D frame
  const m = lookAt(camEye(), [V3.cam.tx, V3.cam.ty, V3.cam.tz], Math.abs(Math.cos(V3.cam.pitch)) < 1e-3 ? [Math.cos(V3.cam.yaw + Math.PI), Math.sin(V3.cam.yaw + Math.PI), 0] : [0, 0, 1]);
  return [[m[0], m[4], m[8]], [m[1], m[5], m[9]], [m[2], m[6], m[10]]];
}
export function lights() {   // the key light from the camera's upper left, the fill from the right and below (c0301)
  const [r, u, b] = camBasis(), mix = (a, c, d) => { const v = [0, 1, 2].map(i => a * r[i] + c * u[i] + d * b[i]), l = Math.hypot(...v); return v.map(x => x / l); };
  return [mix(-0.45, 0.55, 0.7), mix(0.6, -0.35, 0.4)];
}
export function resize3D() { glc.width = Math.max(1, Math.round(W * dpr)); glc.height = Math.max(1, Math.round(H * dpr)); draw3D(); }
export function draw3D() {
  if (!V3.built || !st.mode3d) return;
  const gl = V3.gl, L = V3.loc; gl.viewport(0, 0, glc.width, glc.height); gl.clearColor(0.08, 0.09, 0.11, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  gl.enable(gl.DEPTH_TEST); gl.useProgram(V3.prog); gl.uniformMatrix4fv(L.uM, false, new Float32Array(mvp()));
  const [key, fill] = lights(); gl.uniform3fv(L.uL, key); gl.uniform3fv(L.uL2, fill);
  const parts = V3.board ? [...V3.parts] : []; if (V3.bodies && V3.bodyPart) parts.push(V3.bodyPart);
  for (const p of parts) {
    gl.bindBuffer(gl.ARRAY_BUFFER, p.buf); const F = 44;
    gl.vertexAttribPointer(L.aP, 3, gl.FLOAT, false, F, 0); gl.enableVertexAttribArray(L.aP);
    gl.vertexAttribPointer(L.aN, 3, gl.FLOAT, false, F, 12); gl.enableVertexAttribArray(L.aN);
    gl.vertexAttribPointer(L.aC, 3, gl.FLOAT, false, F, 24); gl.enableVertexAttribArray(L.aC);
    gl.vertexAttribPointer(L.aT, 2, gl.FLOAT, false, F, 36); gl.enableVertexAttribArray(L.aT);
    gl.uniform1f(L.uTex, p.tex ? 1 : 0); if (p.tex) { gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, V3.tex[p.tex]); gl.uniform1i(L.uS, 0); }
    gl.drawArrays(gl.TRIANGLES, 0, p.n);
  }
  for (const k of ["aP", "aN", "aC", "aT"]) gl.disableVertexAttribArray(L[k]);
  drawCube();
  if (!V3.bodies || !V3.meshBufs) return;
  const ML = V3.mloc; gl.useProgram(V3.mprog); gl.uniformMatrix4fv(ML.uVP, false, new Float32Array(mvp())); gl.uniform3fv(ML.uL, key); gl.uniform3fv(ML.uL2, fill);
  (S.bodies || []).forEach((bd, i) => { const mb = bd.mesh && V3.meshBufs[bd.mesh]; if (!mb || notFitted(bd.ref)) return;
    gl.uniformMatrix4fv(ML.uW, false, new Float32Array(bd.m)); gl.uniform3fv(ML.uBody, hexRGB(MESH_BODY));
    gl.uniform1f(ML.uSel, (i === V3.selBody || (st.selComp >= 0 && bd.comp === st.selComp)) ? 1 : 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, mb.pos); gl.vertexAttribPointer(ML.aP, 3, gl.FLOAT, false, 0, 0); gl.enableVertexAttribArray(ML.aP);
    gl.bindBuffer(gl.ARRAY_BUFFER, mb.nrm); gl.vertexAttribPointer(ML.aN, 3, gl.FLOAT, false, 0, 0); gl.enableVertexAttribArray(ML.aN);
    gl.bindBuffer(gl.ARRAY_BUFFER, mb.col); gl.vertexAttribPointer(ML.aC, 4, gl.UNSIGNED_BYTE, true, 0, 0); gl.enableVertexAttribArray(ML.aC);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mb.idx); gl.drawElements(gl.TRIANGLES, mb.n, mb.type, 0); });
  for (const k of ["aP", "aN", "aC"]) gl.disableVertexAttribArray(ML[k]);
}
export function set3D(on) {
  st.mode3d = on; refreshToolbar();
  glc.style.display = on ? "block" : "none"; cv.style.display = on ? "none" : "block"; $("cube").style.display = on ? "block" : "none";
  document.body.classList.toggle("mode3d", on); refreshDock();
  if (on) { measure(); if (!V3.built && !build3D()) { set3D(false); return; } resize3D(); } else { setFitted(false); resize(); }
}
export const PRESETS = { top: [-Math.PI / 2, 1.5699], bottom: [-Math.PI / 2, -1.5699], front: [-Math.PI / 2, 0], back: [Math.PI / 2, 0], left: [Math.PI, 0], right: [0, 0], iso: [-2.2, 0.75] };
export function camPreset(kind, animate = false) {   // the six faces, iso, and a corner given as [yaw, pitch]
  const [yaw, pitch] = Array.isArray(kind) ? kind : PRESETS[kind] || PRESETS.iso, c = V3.cam, b = S.bounds;
  const to = { yaw, pitch, tx: (b[0] + b[2]) / 2, ty: -(b[1] + b[3]) / 2, tz: 0, dist: Math.max(b[2] - b[0], b[3] - b[1]) * 1.7 };
  cancelAnimationFrame(V3.anim);
  if (!animate) { Object.assign(c, to); draw3D(); return; }
  const from = { ...c }, dy = Math.atan2(Math.sin(to.yaw - from.yaw), Math.cos(to.yaw - from.yaw)), t0 = performance.now();
  const step = now => { const k = Math.min(1, (now - t0) / 250), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    c.yaw = from.yaw + dy * e; c.pitch = from.pitch + (to.pitch - from.pitch) * e;
    for (const key of ["tx", "ty", "tz", "dist"]) c[key] = from[key] + (to[key] - from[key]) * e;
    draw3D(); if (k < 1) V3.anim = requestAnimationFrame(step); else c.yaw = to.yaw; };
  V3.anim = requestAnimationFrame(step);
}
export function set3DOption(key, on) {   // the 3D panel's toggles: bodies, board, silkscreen and copper textures
  V3[key] = on; if ((key === "silk" || key === "copper") && V3.built) { const gl = V3.gl; for (const k of Object.keys(V3.tex)) gl.deleteTexture(V3.tex[k]);
    V3.tex.top = sideTexture("top"); V3.tex.bottom = sideTexture("bottom"); }
  draw3D();
}
export let drag3 = null;
glc.addEventListener("mousedown", e => { cancelAnimationFrame(V3.anim); drag3 = { x: e.offsetX, y: e.offsetY, pan: e.shiftKey || e.button === 2, cam: { ...V3.cam } }; glc.style.cursor = "grabbing"; });
glc.addEventListener("contextmenu", e => e.preventDefault());
glc.addEventListener("mousemove", e => { if (!drag3) return; const dx = e.offsetX - drag3.x, dy = e.offsetY - drag3.y, c = V3.cam, c0 = drag3.cam;
  if (drag3.pan) { const k = c.dist / H, f = Math.sin(c.pitch);
    c.tx = c0.tx - (-dx * Math.sin(c.yaw) - dy * f * Math.cos(c.yaw)) * k; c.ty = c0.ty - (dx * Math.cos(c.yaw) - dy * f * Math.sin(c.yaw)) * k; c.tz = c0.tz + dy * Math.cos(c.pitch) * k; }
  else { c.yaw = c0.yaw - dx * 0.008; c.pitch = Math.max(-1.5699, Math.min(1.5699, c0.pitch + dy * 0.008)); }
  draw3D(); });
window.addEventListener("mouseup", e => { if (!drag3) return; const d = drag3; drag3 = null; glc.style.cursor = "grab";
  if (e.target !== glc || Math.abs(e.offsetX - d.x) + Math.abs(e.offsetY - d.y) > 3) return;
  const i = pick3D(e.offsetX, e.offsetY); V3.selBody = i; st.selComp = i >= 0 ? S.bodies[i].comp : -1; rebuildBodies(); draw3D();
  if (i < 0) { showInfo(null); return; }
  const bd = S.bodies[i], how = bd.render === "model" ? "model placed as the file places it" : bd.render === "fitted" ? `model fitted to the body's outline (${bd.fit})` : `extruded outline${bd.fit ? ` (${bd.fit})` : ""}`;
  inspect(() => imodel("body", S.comps[bd.comp].ref, [isection("3D body", [irow("Model", bd.model || "extruded"), irow("Placement", how),
    irow("Height", `${fmtLen(bd.zs ? bd.zs[0] : bd.z0)} to ${fmtLen(bd.zs ? bd.zs[1] : bd.z1)} from the ${bd.side} face`)]), boardPart(bd.comp)], { subtitle: "3D body", target: { comp: bd.comp, net: -1 } })); });
// the body whose box (outline and height) the ray of a pixel meets first
export function pick3D(X, Y) {
  const M = inv(mvp()), nx = 2 * X / W - 1, ny = 1 - 2 * Y / H;
  const un = v => { const r = [0, 1, 2, 3].map(i => M[i] * v[0] + M[4 + i] * v[1] + M[8 + i] * v[2] + M[12 + i] * v[3]); return [r[0] / r[3], r[1] / r[3], r[2] / r[3]]; };
  const p0 = un([nx, ny, -1, 1]), p1 = un([nx, ny, 1, 1]), d = [p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]], T = S.board3d.thickness;
  let best = -1, bt = Infinity;
  (S.bodies || []).forEach((bd, i) => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (let k = 0; k < bd.ring.length; k += 2) { const q = P3(bd.ring[k], bd.ring[k + 1], 0); x0 = Math.min(x0, q[0]); x1 = Math.max(x1, q[0]); y0 = Math.min(y0, q[1]); y1 = Math.max(y1, q[1]); }
    const za = bd.side === "bottom" ? -bd.z1 : T + bd.z0, zb = bd.side === "bottom" ? -bd.z0 : T + bd.z1;
    let t0 = -Infinity, t1 = Infinity;
    for (const [lo, hi, o, dd] of [[x0, x1, p0[0], d[0]], [y0, y1, p0[1], d[1]], [za, zb, p0[2], d[2]]]) {
      if (Math.abs(dd) < 1e-12) { if (o < lo || o > hi) { t0 = Infinity; break; } continue; }
      let a = (lo - o) / dd, b2 = (hi - o) / dd; if (a > b2) [a, b2] = [b2, a]; t0 = Math.max(t0, a); t1 = Math.min(t1, b2); }
    if (t0 <= t1 && t1 > 0 && t0 < bt) { bt = t0; best = i; } });
  return best;
}

glc.addEventListener("wheel", e => { e.preventDefault(); V3.cam.dist = Math.min(Math.max(V3.cam.dist * Math.exp(e.deltaY * 0.0012), 5), 3000); draw3D(); }, { passive: false });

