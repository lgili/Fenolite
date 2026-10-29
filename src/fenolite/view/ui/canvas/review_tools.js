// ================================================================== review tools (c0189): edge measure, links, marks, SVG, print
const EDGE_C = "#00d0ff";
function toggleEdge() { st.edge = !st.edge; st.epick = []; st.eres = null; $("bEdge").classList.toggle("on", st.edge); draw(); }
function edgeGroup(h) {   // every primitive of the clicked item on its layer: a pad's core and its edge stroke together
  const pr = h.pr; if (!pr[5]) return [pr];
  return (byLayer.get(h.layer.id) || []).map(e => e[0]).filter(q => q[5] === pr[5] && q[4] === pr[4] && q[1] !== "t");
}
function edgeClick(X, Y) {
  const h = pick(X, Y); if (!h) return;
  if (st.epick.length >= 2) { st.epick = []; st.eres = null; }
  st.epick.push({ name: h.pr[5] || h.layer.name, layer: h.layer, prims: edgeGroup(h) });
  if (st.epick.length === 2) { const [a, b] = st.epick; st.eres = edgeBetween(a.prims, b.prims);
    if (st.eres) showInfo(`<b>Edge to edge: ${fmtLen(st.eres.d)}</b><br>${esc(a.name)} (${esc(a.layer.name)}) ↔ ${esc(b.name)} (${esc(b.layer.name)})` +
      (a.layer.id !== b.layer.id ? "<br><i>Two layers: the distance is measured in the plane.</i>" : "")); }
  draw();
}
function drawEdge() {
  if (!st.edge && !st.eres) return; worldTf(); ctx.globalAlpha = 0.9;
  for (const g of st.epick) { const c = newCache(); for (const pr of g.prims) addPrim(c, pr); paintCache(ctx, c, g.layer.id, EDGE_C, 0.55, view.s); }
  const r = st.eres; if (!r) return; ctx.globalAlpha = 1; ctx.strokeStyle = ctx.fillStyle = EDGE_C; ctx.lineWidth = 1.5 / view.s;
  ctx.beginPath(); ctx.moveTo(r.a[0], r.a[1]); ctx.lineTo(r.b[0], r.b[1]); ctx.stroke();
  for (const q of [r.a, r.b]) { ctx.beginPath(); ctx.arc(q[0], q[1], 3 / view.s, 0, 2 * Math.PI); ctx.fill(); }
  const txt = `edge ${fmtLen(r.d)}`; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); const P = w2s(r.b[0], r.b[1]); ctx.font = "600 13px system-ui"; const w = ctx.measureText(txt).width;
  ctx.fillStyle = "#000c"; ctx.fillRect(P[0] + 8, P[1] + 6, w + 12, 20); ctx.fillStyle = EDGE_C; ctx.fillText(txt, P[0] + 14, P[1] + 21); worldTf();
  $("coord").textContent = `measure: ${txt}`;
}
$("bEdge").onclick = toggleEdge;

// ---- deep links: the URL's hash keeps the document, the selection, the view, the unit and the layer
function selName() {
  if (!S) return "";
  if (isSch()) return SCH.selComp >= 0 ? S.comps[SCH.selComp].ref : SCH.selNet >= 0 ? "net:" + S.nets[SCH.selNet].name : "";
  return st.selComp >= 0 ? S.comps[st.selComp].ref : st.selNet >= 0 ? "net:" + S.nets[st.selNet] : "";
}
function linkHash() { if (!DOC) return "";
  const q = new URLSearchParams({ doc: DOC.id }); const sel = selName(); if (sel) q.set("sel", sel);
  if (PREVIEW_MODE) { q.set("preview","1"); if (LIB && LIBSEL >= 0) q.set("item",LIB.items[LIBSEL].name); }
  q.set("z", view.s.toFixed(3)); q.set("c", `${view.cx.toFixed(4)},${view.cy.toFixed(4)}`); q.set("u", UNIT);
  if (!isSch() && st.cur) q.set("l", st.cur); return q.toString(); }
let linkTimer = null, linkReady = false;
function linkLater() { if (!linkReady || FLOAT) return; clearTimeout(linkTimer); linkTimer = setTimeout(() => { const h = linkHash(); if (h && location.hash.slice(1) !== h) try { history.replaceState(null, "", "#" + h); } catch (e) { /* a sandboxed frame */ } }, 400); }
function applySelect(name) { if (!name || !S) return; const n = name.startsWith("net:") ? name.slice(4) : name; find(n); }
function applyLink(q) {   // after the document of the link is open
  if (q.get("u") === "mil" || q.get("u") === "mm") setUnit(q.get("u"));
  if (q.get("l") && S && S.layers && S.layers.some(l => l.id === q.get("l"))) { st.cur = q.get("l"); vis.set(st.cur, true); buildTabs(); }
  if (q.get("sel")) applySelect(q.get("sel"));
  const z = parseFloat(q.get("z")), c = (q.get("c") || "").split(",").map(Number);
  if (z > 0 && c.length === 2 && c.every(Number.isFinite)) { view.s = z; view.cx = c[0]; view.cy = c[1]; fitted = true; }
  draw();
}
$("bLink").onclick = async () => { const h = linkHash(); try { history.replaceState(null, "", "#" + h); } catch (e) { /* ignore */ }
  try { await navigator.clipboard.writeText(location.href); $("live").textContent = "link copied"; } catch (e) { showInfo(`<b>Link to this view</b><br><input id="linkText" readonly value="${esc(location.href)}" aria-label="Link to this view" style="width:100%">`); const l = $("linkText"); if (l) { l.focus(); l.select(); } } };

// ---- review marks: kept by the server in the --marks file, else in this browser until downloaded
let MARKS = [];
const marksKey = () => "fenolite.view.marks:" + (PROJECT ? PROJECT.name : "");
const serverMarks = () => LIVE && PROJECT && PROJECT.marks_file;
function loadMarks(given) {
  MARKS = Array.isArray(given) ? given : [];
  if (!serverMarks()) try { const kept = JSON.parse(localStorage.getItem(marksKey()) || "null"); if (Array.isArray(kept)) { const ids = new Set(MARKS.map(m => m.id)); MARKS = MARKS.concat(kept.filter(m => !ids.has(m.id))); } } catch (e) { /* no storage */ }
}
async function sendMark(body) {   // the server writes the file; an exported page keeps the marks here
  if (serverMarks()) {
    const r = await fetch("marks", { method: "POST", headers: { "Content-Type": "application/json", "X-Fenolite-Review": "1" }, body: JSON.stringify(body) });
    const reply = await r.json(); if (!r.ok) { showInfo(`Mark not saved: ${esc(reply.error || r.status)}`); return; } MARKS = reply.marks;
  } else {
    MARKS = MARKS.filter(m => m.id !== body.id); if (body.note !== null) MARKS.push(body);
    try { localStorage.setItem(marksKey(), JSON.stringify(MARKS)); } catch (e) { /* no storage */ }
  }
  buildMarks(); draw();
}
function markClick(x, y) { openMarkEditor(x, y); }
// c0245: the note of a new mark is typed in a small form beside the click, not in a modal prompt
function openMarkEditor(x, y) {
  let box = $("markEditor");
  if (!box) {
    box = document.createElement("form"); box.id = "markEditor"; box.className = "inline-editor"; box.setAttribute("aria-label", "Note for this mark");
    box.innerHTML = `<label for="markNote">Note for this mark</label><input id="markNote" autocomplete="off"><button type="submit">Save</button><button type="button" id="markCancel">Cancel</button>`;
    $("wrap").appendChild(box);
    $("markCancel").onclick = () => closeMarkEditor(true);
    $("markNote").addEventListener("keydown", ev => { if (ev.key === "Escape") { ev.preventDefault(); closeMarkEditor(true); } });
  }
  const [X, Y] = w2s(x, y), r = $("wrap").getBoundingClientRect();
  box.style.left = Math.max(4, Math.min(X + 12, r.width - 300)) + "px"; box.style.top = Math.max(4, Math.min(Y + 12, r.height - 44)) + "px";
  box.hidden = false; $("markNote").value = "";
  box.onsubmit = ev => { ev.preventDefault(); const note = $("markNote").value; closeMarkEditor(false); addMark(x, y, note); };
  $("markNote").focus();
}
function closeMarkEditor(refocus) { const box = $("markEditor"); if (!box || box.hidden) return; box.hidden = true; if (refocus) cv.focus(); }
function addMark(x, y, note) {
  const body = { id: "m" + Date.now().toString(36), doc: DOC.name, x_nm: Math.round(x * 1e6), y_nm: Math.round(y * 1e6), note, select: selName(), created: new Date().toISOString() };
  pushUndo({ label: "add review mark", undo: () => sendMark({ id: body.id, note: null }), redo: () => sendMark(body) });
  return sendMark(body);
}
function deleteMark(m, i) {   // at once, with undo (Ctrl+Z), instead of a modal confirmation
  pushUndo({ label: `delete mark ${i + 1}`, undo: () => sendMark(m), redo: () => sendMark({ id: m.id, note: null }) });
  say(`Mark ${i + 1} deleted · Undo: Ctrl+Z`);
  return sendMark({ id: m.id, note: null });
}
function drawMarks() {
  if (!DOC || !MARKS.length) return; if (!isSch()) worldTf(); ctx.globalAlpha = 1;
  MARKS.forEach((m, i) => { if (m.doc !== DOC.name) return; const x = m.x_nm / 1e6, y = m.y_nm / 1e6, r = 7 / view.s;
    ctx.fillStyle = "#ffd400"; ctx.strokeStyle = "#000"; ctx.lineWidth = 1 / view.s;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - r * 0.8, y - r * 1.6); ctx.arc(x, y - r * 2, r, Math.PI * 0.8, Math.PI * 0.2); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#000"; ctx.font = `600 ${(10 / view.s).toFixed(4)}px system-ui`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(String(i + 1), x, y - r * 2);
    ctx.textAlign = "start"; ctx.textBaseline = "alphabetic"; });
}
function buildMarks() {
  const box = $("marksList"); box.innerHTML = ""; $("marksTitle").style.display = MARKS.length || !LIVE ? "" : "none";
  $("marksTitle").textContent = `Marks (${MARKS.length})` + (serverMarks() ? "" : " · in this browser");
  MARKS.forEach((m, i) => { const d = document.createElement("div"); d.className = "navi";
    d.innerHTML = `${i + 1}. ${esc(m.note || "(no note)")} <small>${esc(m.doc)}${m.select ? " · " + esc(m.select) : ""}</small> <a href="#" title="Delete this mark">×</a>`;
    d.querySelector("a").onclick = ev => { ev.preventDefault(); ev.stopPropagation(); deleteMark(m, i); };
    d.onclick = async () => { const doc = allDocs().find(x => x.name === m.doc);
      if (doc && doc !== DOC) { const shown = await openDoc(doc); if (!shown || shown !== navigation) return; } if (st.mode3d) set3D(false);
      const x = m.x_nm / 1e6, y = m.y_nm / 1e6, e = isSch() ? 25 : 5; fit([x - e, y - e, x + e, y + e]); showInfo(`<b>Mark ${i + 1}</b><br>${esc(m.note)}${m.select ? `<br>On: ${esc(m.select)}` : ""}<br><small>${esc(m.created)}</small>`); };
    box.appendChild(d); });
  if (!serverMarks()) { const b = document.createElement("button"); b.textContent = "Download marks"; b.title = "Save them as a fenolite.review.v0 file for fenolite view --marks";
    b.onclick = () => download(JSON.stringify({ schema: "fenolite.review.v0", marks: MARKS }, null, 2) + "\n", "review.json", "application/json"); box.appendChild(b); }
}
$("bMark").onclick = () => toggle("marking", "bMark");
function download(text, name, type) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.appendChild(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000); }

// ---- SVG: the view drawn again into a recorder of the canvas calls the page makes, as vector paths
class RecPath {   // what a Path2D records, replayed under the transform of the fill or stroke
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
const SVG_NS = ["http:", "", "www.w3.org", "2000", "svg"].join("/");   // the SVG namespace: a name, never fetched (the page loads nothing)
class SvgCtx {
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
  fill(p, rule) { if (typeof p === "string") { rule = p; p = null; } const d = this._d(p || this.path); if (!d) return;
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
function viewSvg(size) {   // the view as an SVG text; null in 3D
  if (!S || st.mode3d) return null;
  const real = ctx, realDpr = dpr, rec = new SvgCtx(W, H); const board = !isSch();
  ctx = rec; dpr = 1; if (board) { P2D = RecPath; buildCaches(); if (S.diff) S.diff.cache = null; }
  try { draw(); } finally { ctx = real; dpr = realDpr; if (board) { P2D = Path2D; buildCaches(); if (S.diff) S.diff.cache = null; } draw(); }
  return rec.svg(W, H, size);
}
$("bSvg").onclick = () => { const svg = viewSvg(); if (!svg) { showInfo("SVG: leave the 3D view first (D)."); return; } download(svg, (DOC ? DOC.name : "view") + ".svg", "image/svg+xml"); };
function printView() {   // the SVG at the chosen scale, printed from a hidden frame: the print dialog also saves a PDF
  const k = $("printScale").value, size = k === "fit" ? 'width="100%" height="100%" preserveAspectRatio="xMidYMid meet"' : `width="${(W / view.s * +k).toFixed(3)}mm" height="${(H / view.s * +k).toFixed(3)}mm"`;
  const svg = viewSvg(size); if (!svg) { showInfo("Print: leave the 3D view first (D)."); return; }
  const f = document.createElement("iframe"); f.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0"; document.body.appendChild(f);
  const scale = k === "fit" ? "fit to page" : `scale ${k}:1`;
  f.contentDocument.open(); f.contentDocument.write(`<!doctype html><html><head><title>${esc(DOC ? DOC.name : "view")}</title><style>@page { margin: 10mm } html, body { margin: 0; height: 100% } svg { display: block; ${k === "fit" ? "width: 100%; height: 95vh" : ""} } p { font: 9pt system-ui; margin: 2mm 0 0 }</style></head><body>${svg}<p>${esc(DOC ? DOC.name : "")} · ${scale} · Fenolite viewer</p></body></html>`); f.contentDocument.close();
  setTimeout(() => { f.contentWindow.focus(); f.contentWindow.print(); setTimeout(() => f.remove(), 2000); }, 200);
}
$("bPrint").onclick = printView;

