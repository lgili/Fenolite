const glc = $("gl");
const V3 = { gl: null, prog: null, loc: {}, parts: [], tex: {}, built: false, cam: { yaw: -2.2, pitch: 0.75, dist: 260, tx: 0, ty: 0, tz: 0 }, selBody: -1, bodies: true, bodyPart: null };
function shader(gl, type, src) { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; }
function init3D() {
if (V3.gl) return true;
const gl = glc.getContext("webgl", { antialias: true }); if (!gl) { showInfo("This browser has no WebGL: the 3D view is not available."); return false; }
const vs = `attribute vec3 aP; attribute vec3 aN; attribute vec3 aC; attribute vec2 aT; uniform mat4 uM; varying vec3 vN; varying vec3 vC; varying vec2 vT;
    void main(){ gl_Position = uM * vec4(aP, 1.0); vN = aN; vC = aC; vT = aT; }`;
const fs = `precision mediump float; varying vec3 vN; varying vec3 vC; varying vec2 vT; uniform sampler2D uS; uniform float uTex; uniform vec3 uL;
    void main(){ vec4 t = texture2D(uS, vT); if (uTex > 0.5 && t.a < 0.5) discard; vec3 base = uTex > 0.5 ? t.rgb : vC;
      float d = abs(dot(normalize(vN), uL)); gl_FragColor = vec4(base * (0.42 + 0.58 * d), 1.0); }`;
const p = gl.createProgram(); gl.attachShader(p, shader(gl, gl.VERTEX_SHADER, vs)); gl.attachShader(p, shader(gl, gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
V3.gl = gl; V3.prog = p; for (const k of ["aP", "aN", "aC", "aT"]) V3.loc[k] = gl.getAttribLocation(p, k);
for (const k of ["uM", "uS", "uTex", "uL"]) V3.loc[k] = gl.getUniformLocation(p, k);
V3.u32 = !!gl.getExtension("OES_element_index_uint");
const mvs = `attribute vec3 aP; attribute vec3 aN; attribute vec4 aC; uniform mat4 uVP; uniform mat4 uW; varying vec3 vN; varying vec4 vC;
    void main(){ gl_Position = uVP * uW * vec4(aP, 1.0); vN = (uW * vec4(aN, 0.0)).xyz; vC = aC; }`;
const mfs = `precision mediump float; varying vec3 vN; varying vec4 vC; uniform vec3 uBody; uniform float uSel; uniform vec3 uL;
    void main(){ vec3 base = vC.a > 0.5 ? vC.rgb : uBody; if (uSel > 0.5) base = mix(base, vec3(1.0, 0.85, 0.3), 0.55);
      float d = abs(dot(normalize(vN), uL)); gl_FragColor = vec4(base * (0.42 + 0.58 * d), 1.0); }`;
const q = gl.createProgram(); gl.attachShader(q, shader(gl, gl.VERTEX_SHADER, mvs)); gl.attachShader(q, shader(gl, gl.FRAGMENT_SHADER, mfs)); gl.linkProgram(q);
V3.mprog = q; V3.mloc = {}; for (const k of ["aP", "aN", "aC"]) V3.mloc[k] = gl.getAttribLocation(q, k);
for (const k of ["uVP", "uW", "uBody", "uSel", "uL"]) V3.mloc[k] = gl.getUniformLocation(q, k);
return true;
}
function b64(text, Type) { const bin = atob(text), u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i); return new Type(u8.buffer); }
function buildMeshes() {
const gl = V3.gl; for (const m of Object.values(V3.meshBufs || {})) for (const k of ["pos", "nrm", "col", "idx"]) gl.deleteBuffer(m[k]);
V3.meshBufs = {};
for (const [key, ms] of Object.entries(S.meshes || {})) {
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
function hexRGB(h) { const n = parseInt(h.slice(1), 16); return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255]; }
function makePart(data, tex) { const gl = V3.gl, b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
return { buf: b, n: data.length / 11, tex }; }
function push(arr, p, n, c, t) { arr.push(p[0], p[1], p[2], n[0], n[1], n[2], c[0], c[1], c[2], t ? t[0] : 0, t ? t[1] : 0); }
function quad(arr, a, b, c2, d, col) { const ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2], vx = d[0] - a[0], vy = d[1] - a[1], vz = d[2] - a[2];
const n = [uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx]; for (const p of [a, b, c2, a, c2, d]) push(arr, p, n, col); }
function P3(x, y, z) { return [x, -y, z]; }
function sideTexture(side) {
const b = S.bounds, w = b[2] - b[0], h = b[3] - b[1], maxT = V3.gl.getParameter(V3.gl.MAX_TEXTURE_SIZE);
const ppm = Math.min(16, (Math.min(maxT, 8192) - 2) / Math.max(w, h)), cw = Math.ceil(w * ppm), ch = Math.ceil(h * ppm);
const c = document.createElement("canvas"); c.width = cw; c.height = ch; const g = c.getContext("2d");
g.setTransform(ppm, 0, 0, ppm, -b[0] * ppm, -b[1] * ppm);
g.fillStyle = "#1d5f33"; g.fill(boardPath(), "evenodd");
g.save(); g.clip(boardPath(), "evenodd");
const pre = side === "top" ? "F." : "B.";
const lay = id => S.layers.find(l => l.id === id);
if (lay(pre + "Cu")) paintCache(g, cache.get(pre + "Cu"), pre + "Cu", "#2b8a45", 1, ppm);
if (lay(pre + "Mask")) paintCache(g, cache.get(pre + "Mask"), pre + "Mask", "#d4b05c", 1, ppm);
if (lay(pre + "SilkS")) { paintCache(g, cache.get(pre + "SilkS"), pre + "SilkS", "#f1f1ea", 1, ppm); paintTexts(g, pre + "SilkS", "#f1f1ea", 1, ppm); }
if (lay("View.Drill")) paintCache(g, cache.get("View.Drill"), "View.Drill", "#0b0b0b", 1, ppm);
g.restore();
const gl = V3.gl, t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t); gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
return t;
}
function bodyGeometry(arr, bd, col) {
const T = S.board3d.thickness, dn = bd.side === "bottom";
const zA = dn ? -bd.z0 : T + bd.z0, zB = dn ? -bd.z1 : T + bd.z1, ring = [];
for (let i = 0; i < bd.ring.length; i += 2) ring.push([bd.ring[i], bd.ring[i + 1]]);
const n = ring.length; if (n < 3) return;
for (let i = 0; i < n; i++) { const a = ring[i], b = ring[(i + 1) % n]; quad(arr, P3(a[0], a[1], zA), P3(b[0], b[1], zA), P3(b[0], b[1], zB), P3(a[0], a[1], zB), col); }
let cx = 0, cy = 0; for (const p of ring) { cx += p[0]; cy += p[1]; } cx /= n; cy /= n;
const cap = col.map(v => v + (1 - v) * 0.18);
for (let i = 0; i < n; i++) { const a = ring[i], b = ring[(i + 1) % n]; for (const p of [[cx, cy], a, b]) push(arr, P3(p[0], p[1], zB), [0, 0, dn ? -1 : 1], cap); }
}
function build3D() {
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
const BODY = "#3c4048", BODY_SEL = "#ffd84d", MESH_BODY = "#9aa0a8";
function rebuildBodies() {
const gl = V3.gl; if (!gl) return; if (V3.bodyPart) gl.deleteBuffer(V3.bodyPart.buf);
const arr = []; (S.bodies || []).forEach((bd, i) => { if (notFitted(bd.ref)) return; if (bd.mesh && V3.meshBufs && V3.meshBufs[bd.mesh]) return;
const sel = i === V3.selBody || (st.selComp >= 0 && bd.comp === st.selComp);
bodyGeometry(arr, bd, hexRGB(sel ? BODY_SEL : BODY)); });
V3.bodyPart = arr.length ? makePart(arr, null) : null;
}
function mul(a, b) { const o = new Array(16); for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) { let s = 0; for (let k = 0; k < 4; k++) s += a[k * 4 + j] * b[i * 4 + k]; o[i * 4 + j] = s; } return o; }
function persp(f, a, n, fa) { const t = 1 / Math.tan(f / 2); return [t / a, 0, 0, 0, 0, t, 0, 0, 0, 0, (fa + n) / (n - fa), -1, 0, 0, 2 * fa * n / (n - fa), 0]; }
function lookAt(e, c, u) { let z = [e[0] - c[0], e[1] - c[1], e[2] - c[2]]; let l = Math.hypot(...z); z = z.map(v => v / l);
let x = [u[1] * z[2] - u[2] * z[1], u[2] * z[0] - u[0] * z[2], u[0] * z[1] - u[1] * z[0]]; l = Math.hypot(...x) || 1; x = x.map(v => v / l);
const y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]];
return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -(x[0] * e[0] + x[1] * e[1] + x[2] * e[2]), -(y[0] * e[0] + y[1] * e[1] + y[2] * e[2]), -(z[0] * e[0] + z[1] * e[1] + z[2] * e[2]), 1]; }
function camEye() { const c = V3.cam; return [c.tx + c.dist * Math.cos(c.pitch) * Math.cos(c.yaw), c.ty + c.dist * Math.cos(c.pitch) * Math.sin(c.yaw), c.tz + c.dist * Math.sin(c.pitch)]; }
function mvp() { const c = V3.cam, e = camEye(), up = Math.abs(Math.cos(c.pitch)) < 1e-3 ? [Math.cos(c.yaw + Math.PI), Math.sin(c.yaw + Math.PI), 0] : [0, 0, 1];
return mul(persp(0.75, Math.max(W, 1) / Math.max(H, 1), c.dist * 0.01, c.dist * 10), lookAt(e, [c.tx, c.ty, c.tz], up)); }
function resize3D() { glc.width = Math.max(1, Math.round(W * dpr)); glc.height = Math.max(1, Math.round(H * dpr)); draw3D(); }
function draw3D() {
if (!V3.built || !st.mode3d) return;
const gl = V3.gl, L = V3.loc; gl.viewport(0, 0, glc.width, glc.height); gl.clearColor(0.08, 0.09, 0.11, 1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
gl.enable(gl.DEPTH_TEST); gl.useProgram(V3.prog); gl.uniformMatrix4fv(L.uM, false, new Float32Array(mvp()));
const e = camEye(), c = V3.cam, lv = [e[0] - c.tx, e[1] - c.ty, e[2] - c.tz + c.dist * 0.6], ll = Math.hypot(...lv); gl.uniform3fv(L.uL, lv.map(v => v / ll));
const parts = [...V3.parts]; if (V3.bodies && V3.bodyPart) parts.push(V3.bodyPart);
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
if (!V3.bodies || !V3.meshBufs) return;
const ML = V3.mloc; gl.useProgram(V3.mprog); gl.uniformMatrix4fv(ML.uVP, false, new Float32Array(mvp())); gl.uniform3fv(ML.uL, lv.map(v => v / ll));
(S.bodies || []).forEach((bd, i) => { const mb = bd.mesh && V3.meshBufs[bd.mesh]; if (!mb || notFitted(bd.ref)) return;
gl.uniformMatrix4fv(ML.uW, false, new Float32Array(bd.m)); gl.uniform3fv(ML.uBody, hexRGB(MESH_BODY));
gl.uniform1f(ML.uSel, (i === V3.selBody || (st.selComp >= 0 && bd.comp === st.selComp)) ? 1 : 0);
gl.bindBuffer(gl.ARRAY_BUFFER, mb.pos); gl.vertexAttribPointer(ML.aP, 3, gl.FLOAT, false, 0, 0); gl.enableVertexAttribArray(ML.aP);
gl.bindBuffer(gl.ARRAY_BUFFER, mb.nrm); gl.vertexAttribPointer(ML.aN, 3, gl.FLOAT, false, 0, 0); gl.enableVertexAttribArray(ML.aN);
gl.bindBuffer(gl.ARRAY_BUFFER, mb.col); gl.vertexAttribPointer(ML.aC, 4, gl.UNSIGNED_BYTE, true, 0, 0); gl.enableVertexAttribArray(ML.aC);
gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, mb.idx); gl.drawElements(gl.TRIANGLES, mb.n, mb.type, 0); });
for (const k of ["aP", "aN", "aC"]) gl.disableVertexAttribArray(ML[k]);
}
function set3D(on) {
st.mode3d = on; $("b3d").classList.toggle("on", on);
glc.style.display = on ? "block" : "none"; cv.style.display = on ? "none" : "block"; $("bar3d").style.display = on ? "flex" : "none";
if (on) { measure(); if (!V3.built && !build3D()) { set3D(false); return; } resize3D(); } else { fitted = false; resize(); }
}
function camPreset(kind) { const c = V3.cam; if (kind === "top") { c.yaw = -Math.PI / 2; c.pitch = 1.5699; } else if (kind === "bottom") { c.yaw = -Math.PI / 2; c.pitch = -1.5699; }
else { c.yaw = -2.2; c.pitch = 0.75; } const b = S.bounds; c.tx = (b[0] + b[2]) / 2; c.ty = -(b[1] + b[3]) / 2; c.tz = 0; c.dist = Math.max(b[2] - b[0], b[3] - b[1]) * 1.7; draw3D(); }
let drag3 = null;
glc.addEventListener("mousedown", e => { drag3 = { x: e.offsetX, y: e.offsetY, pan: e.shiftKey || e.button === 2, cam: { ...V3.cam } }; glc.style.cursor = "grabbing"; });
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
const bd = S.bodies[i], how = bd.render === "model" ? "model placed as the file places it" : bd.render === "fitted" ? `model fitted to the body's outline (${esc(bd.fit)})` : `extruded outline${bd.fit ? ` (${esc(bd.fit)})` : ""}`;
showInfo(compInfo(bd.comp) + `<br>Body: ${esc(bd.model || "extruded")} · ${how}<br>Height: ${(bd.zs ? bd.zs[0] : bd.z0).toFixed(2)} to ${(bd.zs ? bd.zs[1] : bd.z1).toFixed(2)} mm from the ${bd.side} face`); });
function pick3D(X, Y) {
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
function inv(a) { const o = new Array(16);
const b00 = a[0] * a[5] - a[1] * a[4], b01 = a[0] * a[6] - a[2] * a[4], b02 = a[0] * a[7] - a[3] * a[4], b03 = a[1] * a[6] - a[2] * a[5], b04 = a[1] * a[7] - a[3] * a[5], b05 = a[2] * a[7] - a[3] * a[6];
const b06 = a[8] * a[13] - a[9] * a[12], b07 = a[8] * a[14] - a[10] * a[12], b08 = a[8] * a[15] - a[11] * a[12], b09 = a[9] * a[14] - a[10] * a[13], b10 = a[9] * a[15] - a[11] * a[13], b11 = a[10] * a[15] - a[11] * a[14];
const det = 1 / (b00 * b11 - b01 * b10 + b02 * b09 + b03 * b08 - b04 * b07 + b05 * b06);
o[0] = (a[5] * b11 - a[6] * b10 + a[7] * b09) * det; o[1] = (a[2] * b10 - a[1] * b11 - a[3] * b09) * det; o[2] = (a[13] * b05 - a[14] * b04 + a[15] * b03) * det; o[3] = (a[10] * b04 - a[9] * b05 - a[11] * b03) * det;
o[4] = (a[6] * b08 - a[4] * b11 - a[7] * b07) * det; o[5] = (a[0] * b11 - a[2] * b08 + a[3] * b07) * det; o[6] = (a[14] * b02 - a[12] * b05 - a[15] * b01) * det; o[7] = (a[8] * b05 - a[10] * b02 + a[11] * b01) * det;
o[8] = (a[4] * b10 - a[5] * b08 + a[7] * b06) * det; o[9] = (a[1] * b08 - a[0] * b10 - a[3] * b06) * det; o[10] = (a[12] * b04 - a[13] * b02 + a[15] * b00) * det; o[11] = (a[9] * b02 - a[8] * b04 - a[11] * b00) * det;
o[12] = (a[5] * b07 - a[4] * b09 - a[6] * b06) * det; o[13] = (a[0] * b09 - a[1] * b07 + a[2] * b06) * det; o[14] = (a[13] * b01 - a[12] * b03 - a[14] * b00) * det; o[15] = (a[8] * b03 - a[9] * b01 + a[10] * b00) * det;
return o; }
glc.addEventListener("wheel", e => { e.preventDefault(); V3.cam.dist = Math.min(Math.max(V3.cam.dist * Math.exp(e.deltaY * 0.0012), 5), 3000); draw3D(); }, { passive: false });
$("v3top").onclick = () => camPreset("top");
$("v3bot").onclick = () => camPreset("bottom");
$("v3iso").onclick = () => camPreset("iso");
$("c3body").onchange = e => { V3.bodies = e.target.checked; draw3D(); };
