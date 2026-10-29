// ================================================================== schematic view (scene kind "schematic")
// A sheet drawn as Altium Designer draws it: the file's own colours and fonts on its paper, a line grid, a grey
// workspace around it. Units on the page are millimetres, Y downwards from the sheet's top-left corner.
const SCH = { sel: -1, selNet: -1, selComp: -1, images: new Map(), byObj: null, filter: "" };
const WORKSPACE = "#4a4d52", SEL = "#00b050";
const isSch = () => !!(S && S.kind === "schematic");
const MIL = 0.0254;
function toMMsch(sc) {
  if (sc.mm) return sc; diffToMM(sc); checkToMM(sc);
  const f = v => v * MM, fb = b => b ? b.map(f) : b;
  for (const p of sc.prims) { if (p.p) p.p = p.p.map(f); if (p.b) p.b = p.b.map(f);
    for (const k of ["x", "y", "rx", "ry", "w", "m", "sz", "gw", "th"]) if (typeof p[k] === "number") p[k] = p[k] * MM;
    if (p.rr) p.rr = p.rr.map(f); p.bb = primBox(p); }
  for (const o of sc.objects) o.b = fb(o.b);
  for (const c of sc.comps) c.b = fb(c.b);
  for (const fo of sc.fonts) fo.emm = fo.em * MM;
  const sh = sc.sheet; for (const k of ["w", "h", "grid", "margin", "x0", "y0"]) if (typeof sh[k] === "number") sh[k] *= MM;
  sh.x0 = sh.x0 || 0; sh.y0 = sh.y0 || 0; sh.origin = sh.origin ? sh.origin.map(f) : [0, sh.h];
  if (sh.text === "stroke") sc.comps.forEach(c => { c.hidden = c.ref.startsWith("#"); });
  sc.bounds = sc.bounds.map(f); sc.mm = true; return sc;
}
function primBox(p) {
  const w = (p.w || 0) / 2;
  if (p.k === "l" || p.k === "g" || p.k === "b") { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (let i = 0; i < p.p.length; i += 2) { x0 = Math.min(x0, p.p[i]); x1 = Math.max(x1, p.p[i]); y0 = Math.min(y0, p.p[i + 1]); y1 = Math.max(y1, p.p[i + 1]); }
    return [x0 - w, y0 - w, x1 + w, y1 + w]; }
  if (p.k === "r" || p.k === "x" || p.k === "i") return [p.b[0] - w, p.b[1] - w, p.b[2] + w, p.b[3] + w];
  if (p.k === "e" || p.k === "a") return [p.x - p.rx - w, p.y - p.ry - w, p.x + p.rx + w, p.y + p.ry + w];
  return null;   // texts: measured when drawn
}
function fontCss(fo, px) { return `${fo.italic ? "italic " : ""}${fo.bold ? "bold " : ""}${px.toFixed(2)}px "${fo.name}", "Times New Roman", Times, serif`; }
function schAlpha(p) {
  if (SCH.selNet < 0) return 1;
  const o = p.o >= 0 ? S.objects[p.o] : null;
  return o && o.net === SCH.selNet ? 1 : 0.22;
}
function dashOf(d, w) { const u = Math.max(w, 0.1); return d === 1 ? [u * 4, u * 3] : d === 2 ? [u, u * 2] : d === 3 ? [u * 4, u * 2, u, u * 2] : []; }
function lineShape(g, x, y, fx, fy, shape, size, color, w) {   // a line end: arrow, solid arrow, tail, solid tail, circle, square
  const L = [0.5, 1, 1.6, 2.4][size || 0] || 1, a = Math.atan2(y - fy, x - fx), c = Math.cos(a), s = Math.sin(a);
  const P = (u, v) => [x + u * c - v * s, y + u * s + v * c];
  g.beginPath();
  if (shape === 1 || shape === 2) { const [ax, ay] = P(-L, -L / 2), [bx, by] = P(-L, L / 2); g.moveTo(ax, ay); g.lineTo(x, y); g.lineTo(bx, by); if (shape === 2) { g.closePath(); g.fillStyle = color; g.fill(); } g.stroke(); }
  else if (shape === 3 || shape === 4) { const [ax, ay] = P(L, -L / 2), [bx, by] = P(L, L / 2); g.moveTo(ax, ay); g.lineTo(x, y); g.lineTo(bx, by); if (shape === 4) { g.closePath(); g.fillStyle = color; g.fill(); } g.stroke(); }
  else if (shape === 5) { g.arc(x, y, L / 2, 0, 2 * Math.PI); g.fillStyle = color; g.fill(); }
  else if (shape === 6) { g.fillStyle = color; g.fillRect(x - L / 2, y - L / 2, L, L); }
}
function roundRectPath(g, b, rx, ry) {
  const [x0, y0, x1, y1] = b; rx = Math.min(rx, (x1 - x0) / 2); ry = Math.min(ry, (y1 - y0) / 2);
  g.beginPath(); g.moveTo(x0 + rx, y0); g.lineTo(x1 - rx, y0); g.ellipse(x1 - rx, y0 + ry, rx, ry, 0, -Math.PI / 2, 0); g.lineTo(x1, y1 - ry);
  g.ellipse(x1 - rx, y1 - ry, rx, ry, 0, 0, Math.PI / 2); g.lineTo(x0 + rx, y1); g.ellipse(x0 + rx, y1 - ry, rx, ry, 0, Math.PI / 2, Math.PI);
  g.lineTo(x0, y0 + ry); g.ellipse(x0 + rx, y0 + ry, rx, ry, 0, Math.PI, 1.5 * Math.PI); g.closePath();
}
function strokeW(w) { return Math.max(w, 1 / view.s); }
function drawStrokeText(p, alpha) {   // KiCad's way: texts as strokes, in Fenolite's own stroke font
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
function drawText(p, alpha) {
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
function wrapLines(g, text, width, wrap) {
  const out = []; for (const para of text.split("\n")) { if (!wrap) { out.push(para); continue; } let line = "";
    for (const word of para.split(/(\s+)/)) { const t = line + word; if (line && g.measureText(t).width > width) { out.push(line.trimEnd()); line = word.trimStart(); } else line = t; } out.push(line); }
  return out;
}
function drawFrame(p, alpha) {
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
function drawImage(p, alpha) {
  const [x0, y0, x1, y1] = p.b; ctx.globalAlpha = alpha;
  if (p.src) { let im = SCH.images.get(p.src); if (!im) { im = new Image(); im.onload = () => draw(); im.src = p.src; SCH.images.set(p.src, im); }
    if (im.complete && im.naturalWidth) { ctx.drawImage(im, x0, y0, x1 - x0, y1 - y0); return; } }
  ctx.strokeStyle = "#888"; ctx.lineWidth = strokeW(0.1); ctx.strokeRect(x0, y0, x1 - x0, y1 - y0);
  ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1, y1); ctx.moveTo(x1, y0); ctx.lineTo(x0, y1); ctx.stroke();
}
function drawPrim(p, alpha) {
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
function visibleBox() { const [ax, ay] = s2w(0, 0), [bx, by] = s2w(W, H); return [Math.min(ax, bx), Math.min(ay, by), Math.max(ax, bx), Math.max(ay, by)]; }
function drawGrid(sh) {
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
function shade(hex, f) { const n = parseInt(hex.slice(1), 16); const c = [n >> 16, (n >> 8) & 255, n & 255].map(v => Math.round(v * (1 - f))); return `rgb(${c[0]},${c[1]},${c[2]})`; }
function drawSch() {
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.fillStyle = UI_THEME === "light" ? "#c9ccd1" : S.sheet.workspace || WORKSPACE; ctx.fillRect(0, 0, cv.width, cv.height);
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
// --- hit test
function schHitPrim(p, x, y, tol) {
  switch (p.k) {
    case "l": { const q = p.p; if (q.length === 2) return Math.hypot(x - q[0], y - q[1]) <= tol + p.w / 2; for (let i = 0; i + 3 < q.length; i += 2) if (segDist(x, y, q[i], q[i + 1], q[i + 2], q[i + 3]) <= p.w / 2 + tol) return true; return false; }
    case "g": return inRing(x, y, p.p) || p.p.some((_, i) => i % 2 === 0 && i + 3 < p.p.length && segDist(x, y, p.p[i], p.p[i + 1], p.p[i + 2], p.p[i + 3]) <= tol);
    case "r": case "x": case "i": { const b = p.b; return x >= b[0] - tol && x <= b[2] + tol && y >= b[1] - tol && y <= b[3] + tol; }
    case "e": case "a": return ((x - p.x) / (p.rx + tol)) ** 2 + ((y - p.y) / (p.ry + tol)) ** 2 <= 1;
    case "b": { const q = p.p; for (let i = 0; i + 3 < q.length; i += 2) if (segDist(x, y, q[i], q[i + 1], q[i + 2], q[i + 3]) <= p.w / 2 + tol) return true; return false; }
    case "t": { if (!p.sb) return false; const [w, h] = p.sb, c = [1, 0, -1, 0][p.rot || 0], s = [0, 1, 0, -1][p.rot || 0];
      const dx = x - p.x, dy = y - p.y, u = dx * c - dy * s, v = dx * s + dy * c;   // into the text's own frame
      const u0 = p.h === "left" ? 0 : p.h === "right" ? -w : -w / 2, v0 = p.v === "top" ? 0 : p.v === "center" ? -h / 2 : -h;
      return u >= u0 - tol && u <= u0 + w + tol && v >= v0 - tol && v <= v0 + h + tol; }
  }
  return false;
}
const PRIORITY = { pin: 0, wire: 1, bus: 1, entryline: 1, junction: 1, label: 1, power: 1, port: 1, entry: 1, noerc: 1, harnessline: 1, comp: 2, sheet: 2, harness: 2, directive: 2, graphic: 3 };
function schPick(X, Y) {
  const [x, y] = s2w(X, Y), tol = 3 / view.s; let best = -1, bp = 9;
  for (let i = S.prims.length - 1; i >= 0; i--) { const p = S.prims[i]; if (p.o < 0) continue; const b = p.bb;
    if (b && (x < b[0] - tol || x > b[2] + tol || y < b[1] - tol || y > b[3] + tol)) continue;
    if (!schHitPrim(p, x, y, tol)) continue; const pr = PRIORITY[S.objects[p.o].k] ?? 4; if (pr < bp) { bp = pr; best = p.o; if (pr === 0) break; } }
  if (best < 0) for (let i = 0; i < S.comps.length; i++) { const b = S.comps[i].b; if (b && x >= b[0] && x <= b[2] && y >= b[1] && y <= b[3]) { best = S.objects.findIndex(o => o.k === "comp" && o.comp === i); break; } }
  return best;
}
function rows(list) { return `<table>${list.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${linkify(v)}</td></tr>`).join("")}</table>`; }
function compRows(ci) { const c = S.comps[ci]; const r = [["Designator", c.ref], ["Comment", c.comment], ["Design Item ID", c.lib]];
  if (c.b) r.push(["Extent", fmtPair(c.b[2] - c.b[0], c.b[3] - c.b[1])]);
  if (c.description) r.push(["Description", c.description]); if (c.footprint) r.push(["Footprint", c.footprint]);
  const vs = variantOf(c.group || c.ref);
  const params = { ...(c.params || {}), ...((vs && vs.params) || {}) };
  for (const [k, v] of Object.entries(params)) r.push([k, v]);
  if (vs) r.push([`Variant ${VARIANT}`, vs.kind]); return r; }
function schSelect(oi) {
  SCH.sel = oi; SCH.selNet = -1; SCH.selComp = -1;
  if (oi < 0) { showInfo(null); buildNav(); draw(); return; }
  const o = S.objects[oi];
  if (o.k === "comp") { SCH.selComp = o.comp; showInfo(`<b>Properties</b> · Component${rows(compRows(o.comp))}`); }
  else { if (o.net >= 0) SCH.selNet = o.net;
    let html = `<b>Properties</b> · ${esc(o.k)}${rows(o.info)}`;
    if (o.net >= 0) { const n = S.nets[o.net]; html += `<br><b>Net ${esc(n.name || "(no name)")}</b>: ${n.pins.length} pins` + (n.pins.length ? `<br><small>${esc(n.pins.slice(0, 40).join(", "))}${n.pins.length > 40 ? " …" : ""}</small>` : "") + projectNetInfo(n); shareNet(n.project || n.name); }
    if (o.comp >= 0) html += `<br><br><b>Part</b>${rows(compRows(o.comp))}`;
    showInfo(html); }
  buildNav(); draw();
}
function netBox(ni) { let b = null; for (const o of S.objects) if (o.net === ni && o.b) b = b ? [Math.min(b[0], o.b[0]), Math.min(b[1], o.b[1]), Math.max(b[2], o.b[2]), Math.max(b[3], o.b[3])] : [...o.b]; return b; }
