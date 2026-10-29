function flip() { view.mirror = !view.mirror; const b = $("bFlip"), l = b.querySelector(".lbl"); (l || b).textContent = "View: " + (view.mirror ? "Bottom" : "Top"); b.classList.toggle("on", view.mirror); draw(); }
function toggle(key, btn) { st[key] = !st[key]; $(btn).classList.toggle("on", st[key]); if (key === "measure" && !st.measure) st.mpts = []; draw(); }
function find(q) {
  q = q.trim().toLowerCase(); if (!q || !S) return;
  if (isSch()) { schFind(q); return; }
  const ci = S.comps.findIndex(c => c.ref.toLowerCase() === q);
  if (ci >= 0) { st.selComp = ci; st.selNet = -1; const b = S.comps[ci].bbox; if (b) fit([b[0] - 5, b[1] - 5, b[2] + 5, b[3] + 5]); showInfo(compInfo(ci)); draw(); return; }
  const ni = S.nets.findIndex(n => n.toLowerCase() === q);
  if (ni >= 0) { st.selNet = ni; st.selComp = -1; showInfo(`Net: <b>${esc(S.nets[ni])}</b>`); draw(); return; }
  showInfo(`Nothing named <b>${esc(q)}</b> on this board.`);
}
function setSidebar(open) {
  $("app").classList.toggle("sidebar-open", open);
  $("bSidebar").setAttribute("aria-expanded", String(open));
}
$("bSidebar").onclick = () => setSidebar(!$("app").classList.contains("sidebar-open"));
$("b3d").onclick = () => set3D(!st.mode3d);
$("bFit").onclick = () => st.mode3d ? camPreset("iso") : fit();
$("bFlip").onclick = flip;
$("bMeasure").onclick = () => toggle("measure", "bMeasure");
$("bClear").onclick = () => { st.mpts = []; st.selOv = -1; if (isSch()) schSelect(-1); else select(null); };
function zoomBy(f) { view.s = Math.min(Math.max(view.s * f, 0.2), 400); draw(); }
$("opac").oninput = e => { st.opac = e.target.value / 100; draw(); };
$("search").addEventListener("keydown", e => { if (e.key === "Enter") { find(e.target.value); e.target.blur(); } else if (e.key === "Escape") e.target.blur(); });
let drag = null;
cv.addEventListener("mousedown", e => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur();   // shortcuts follow the board
  drag = { x: e.offsetX, y: e.offsetY, cx: view.cx, cy: view.cy, moved: false }; });
window.addEventListener("mouseup", e => { if (!drag) return; const d = drag; drag = null;
  if (d.moved || e.target !== cv) return; const [x, y] = s2w(e.offsetX, e.offsetY);
  if (st.measure) { measureClick(e.offsetX, e.offsetY, e.altKey); return; }
  if (st.marking) { markClick(x, y); return; }
  if (st.edge && !isSch()) { edgeClick(e.offsetX, e.offsetY); return; }
  const fi = pickFinding(e.offsetX, e.offsetY); if (fi >= 0) { selectFinding(fi); return; }   // c0245: a marker selects its message
  for (const pickMarker of MARKER_PICKS) if (pickMarker(e.offsetX, e.offsetY)) return;
  if (isSch()) schSelect(schPick(e.offsetX, e.offsetY)); else select(pick(e.offsetX, e.offsetY), [x, y]); });
cv.addEventListener("dblclick", e => { if (!S) return;
  if (isSch()) { schDouble(e.offsetX, e.offsetY); return; }
  const h = pick(e.offsetX, e.offsetY), ci = h ? h.pr[4] : -1; if (ci >= 0) crossProbe(S.comps[ci].ref, "schematic"); });
cv.addEventListener("contextmenu", e => { if (isSch()) e.preventDefault(); });
function showCoord(x, y) {
  st.mouse = [x, y];
  if (!(st.measure && st.mpts.length)) $("coord").textContent = isSch()
    ? `X ${fmtLen(x - S.sheet.origin[0])}  Y ${fmtLen(S.sheet.origin[1] - y)} · grid ${fmtLen(S.sheet.grid)}` : `x ${fmtLen(x)}  y ${fmtLen(y)}`;
}
cv.addEventListener("mousemove", e => { if (!S) return; const [x, y] = s2w(e.offsetX, e.offsetY);
  showCoord(x, y);
  if (drag) { const dx = e.offsetX - drag.x, dy = e.offsetY - drag.y; if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true;
    view.cx = drag.cx - m() * dx / view.s; view.cy = drag.cy - dy / view.s; drawInteractive(); }
  else if (st.measure) { st.mhover = snap(x, y, e.altKey); drawCursor(); } });   // c0245: on the overlay, without redrawing the board
cv.addEventListener("wheel", e => { e.preventDefault(); const [x, y] = s2w(e.offsetX, e.offsetY); const f = Math.exp(-e.deltaY * 0.0015);
  view.s = Math.min(Math.max(view.s * f, 0.2), 400); const [x2, y2] = s2w(e.offsetX, e.offsetY); view.cx += x - x2; view.cy += y - y2; drawInteractive(); }, { passive: false });
