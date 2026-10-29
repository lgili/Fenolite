function buildFindings() {
const box = $("overlays"); box.innerHTML = "";
const groups = [...(S.meta.findings || [])], byG = new Map();
(S.overlays || []).forEach((o, i) => { const g = ovGroup(o); if (!byG.has(g)) byG.set(g, []); byG.get(g).push(i); });
for (const g of byG.keys()) if (!groups.some(x => x.id === g)) groups.push({ id: g, title: g, color: S.overlays[byG.get(g)[0]].color, n: byG.get(g).length, note: "" });
$("ovTitle").style.display = groups.length ? "block" : "none";
for (const g of groups) {
const idx = byG.get(g.id) || [], row = document.createElement("div"); row.className = "fg" + (idx.length ? "" : " zero"); row.title = g.note || "";
row.innerHTML = `<input type="checkbox" ${st.ovOff.has(g.id) ? "" : "checked"}><span class="sw" style="background:${esc(g.color)}"></span><span class="ft">${st.ovOpen.has(g.id) ? "\u25BE" : "\u25B8"} ${esc(g.title)}</span><span class="fn">${idx.length}</span>`;
row.querySelector("input").onchange = e => { if (e.target.checked) st.ovOff.delete(g.id); else st.ovOff.add(g.id); draw(); };
row.querySelector(".ft").onclick = () => { if (st.ovOpen.has(g.id)) st.ovOpen.delete(g.id); else st.ovOpen.add(g.id); buildFindings(); };
box.appendChild(row);
if (!st.ovOpen.has(g.id)) continue;
if (g.note) { const n = document.createElement("div"); n.className = "fnote"; n.textContent = g.note; box.appendChild(n); }
for (const i of idx) { const d = document.createElement("div"); d.className = "ov" + (i === st.selOv ? " sel" : ""); d.textContent = S.overlays[i].label; d.onclick = () => gotoFinding(i); box.appendChild(d); }
}
}
function gotoFinding(i) {
const o = S.overlays[i]; if (st.mode3d) set3D(false); st.selOv = i; st.selNet = -1; st.selComp = -1; st.ovOff.delete(ovGroup(o));
const xs = o.pts.map(p => p[0]), ys = o.pts.map(p => p[1]);
const b = o.bbox ? [Math.min(o.bbox[0], ...xs), Math.min(o.bbox[1], ...ys), Math.max(o.bbox[2], ...xs), Math.max(o.bbox[3], ...ys)] : [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
if (o.layer && (o.layer.startsWith("B.") !== view.mirror)) flip();
const g = (S.meta.findings || []).find(x => x.id === ovGroup(o));
fit([b[0] - 4, b[1] - 4, b[2] + 4, b[3] + 4]); buildFindings();
showInfo(`<b>${esc(g ? g.title : ovGroup(o))}</b><br>${esc(o.label)}${g && g.note ? `<br><small>${esc(g.note)}</small>` : ""}`);
}
function buildPanels() {
buildFindings();
const c = S.meta.counts || {};
$("notes").innerHTML = (S.meta.notes || []).map(esc).join("<br>") + `${(S.meta.notes || []).length ? "<br>" : ""}Read by the ${esc(S.meta.backend || "?")} backend, evidence ${esc(S.meta.evidence || "?")}.` +
`<br>${c.footprints || 0} parts · ${c.pads || 0} pads · ${c.tracks || 0} tracks · ${c.vias || 0} vias · ${c.zones || 0} zones`;
}
function loadScene(scene, keepView) {
st.mpts = []; st.mhover = null; st.lastHit = null; st.selFinding = -1;
$("tablewrap").style.display = "none"; document.body.classList.remove("table"); cv.style.display = "block";
if (scene.kind === "table") loadTable(scene);
else if (scene.kind === "library") loadLibrary(scene, keepView);
else if (scene.kind === "schematic") loadSch(scene, keepView);
else loadBoard(scene, keepView);
REVIEW.doc = DOC?.id || null; buildProjectReview();
}
function loadBoard(scene, keepView) {
document.body.classList.remove("sch"); st.itemInfo = false;
const first = S === null || S !== scene && !keepView; S = scene;
for (const l of S.layers) if (!vis.has(l.id)) vis.set(l.id, l.visible);
if (!st.cur || !S.layers.some(l => l.id === st.cur)) st.cur = (S.layers.find(l => l.id === "F.Cu") || S.layers[0] || {}).id;
if (st.query) st.query = st.query.text && S.prims ? { text: st.query.text, ...queryRun(S, queryParse(st.query.text)) } : null;
buildCaches(); buildTabs(); buildPanels(); buildDiffList(); buildMessages(); buildVariants(); buildReview(); applyProjNet();
cv.style.display = st.mode3d ? "none" : "block";
$("fname").textContent = S.meta.name; document.title = S.meta.name + " · Fenolite viewer";
$("gen").textContent = S.meta.sha256 ? `SHA-256 ${S.meta.sha256.slice(0, 12)}` : "";
if (V3.built) { V3.built = false; if (st.mode3d) { build3D(); draw3D(); } }
if (first) { fitted = false; fit(); } else draw();
}
