// ================================================================== project nets across sheets and the board (c0185)
let PROJ_NET = null; const BC = !PREVIEW_MODE && "BroadcastChannel" in window ? new BroadcastChannel("fenolite-view") : null;
function shareNet(name) { PROJ_NET = name || null; if (BC) BC.postMessage({ net: PROJ_NET }); }
if (BC) BC.onmessage = e => { PROJ_NET = e.data && e.data.net || null; applyProjNet(); };
function projectNetInfo(n) {
  if (!n.project) return "";
  const others = (n.sheets || []).filter(x => !S.meta || x !== S.meta.name);
  const links = others.map(x => `<a href="#" class="sheetlink" data-sheet="${esc(x)}">${esc(x)}</a>`).join(", ");
  return `<br><br><b>Project net ${esc(n.project)}</b>: ${(n.project_pins || []).length} pins` + (links ? `<br>Also on: ${links}` : "<br>On this sheet only") +
    `<br><small>${esc((n.project_pins || []).slice(0, 60).join(", "))}</small>`;
}
document.addEventListener("click", e => { const a = e.target.closest && e.target.closest(".sheetlink"); if (!a) return; e.preventDefault();
  const d = docByFile(a.dataset.sheet); if (d) openDoc(d); });
function applyProjNet() {   // the shared net, selected on the sheet or board shown
  if (!PROJ_NET || !S) return;
  if (isSch()) { const i = S.nets.findIndex(n => (n.project || n.name) === PROJ_NET); if (i >= 0) selectNet(i, false, true); }
  else if (S.nets && !S.kind) { const i = S.nets.indexOf(PROJ_NET); if (i >= 0) { st.selNet = i; st.selComp = -1; showInfo(`Net: <b>${esc(PROJ_NET)}</b>`); draw(); } }
}
function selectNet(ni, zoom, quiet) { SCH.sel = -1; SCH.selComp = -1; SCH.selNet = ni; const n = S.nets[ni];
  showInfo(`<b>Net ${esc(n.name || "(no name)")}</b>: ${n.pins.length} pins<br><small>${esc(n.pins.join(", "))}</small>` + projectNetInfo(n));
  if (!quiet) shareNet(n.project || n.name);
  const b = netBox(ni); if (zoom && b) fit([b[0] - 8, b[1] - 8, b[2] + 8, b[3] + 8]); else draw(); buildNav(); }
function selectComp(ci, zoom) { const oi = S.objects.findIndex(o => o.k === "comp" && o.comp === ci); schSelect(oi);
  const b = S.comps[ci].b; if (zoom && b) fit([b[0] - 12, b[1] - 12, b[2] + 12, b[3] + 12]); }
function natural(a, b) { return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" }); }
function buildNav() {
  const box = $("navList"); if (!box || !isSch()) return; const q = SCH.filter.trim().toLowerCase(); box.innerHTML = "";
  const comps = S.comps.map((c, i) => [c, i]).filter(([c]) => !c.hidden).filter(([c]) => !q || c.ref.toLowerCase().includes(q) || (c.comment || "").toLowerCase().includes(q)).sort((a, b) => natural(a[0].ref, b[0].ref));
  const nets = S.nets.map((n, i) => [n, i]).filter(([n]) => n.name && (n.pins.length > 1 || !n.name.startsWith("Net")) && (!q || n.name.toLowerCase().includes(q))).sort((a, b) => natural(a[0].name, b[0].name));
  const head = t => { const d = document.createElement("div"); d.className = "navg"; d.textContent = t; box.appendChild(d); };
  head(`Components (${comps.length})`);
  for (const [c, i] of comps) { const d = document.createElement("div"); d.className = "navi" + (SCH.selComp === i ? " sel" : ""); d.innerHTML = `${esc(c.ref)} <small>${esc(c.comment || c.lib || "")}</small>`; d.title = c.description || c.lib || ""; d.onclick = () => selectComp(i, true); box.appendChild(d); }
  head(`Nets (${nets.length})`);
  for (const [n, i] of nets) { const d = document.createElement("div"); d.className = "navi" + (SCH.selNet === i ? " sel" : ""); d.innerHTML = `${esc(n.name)}${n.project && n.project !== n.name ? ` <small>→ ${esc(n.project)}</small>` : ""} <small>${n.pins.length}${n.sheets && n.sheets.length > 1 ? ` · ${n.sheets.length} sheets` : ""}</small>`; d.onclick = () => selectNet(i, true); box.appendChild(d); }
}
$("navFilter").addEventListener("input", e => { SCH.filter = e.target.value; buildNav(); });
function allDocs() { return PROJECT ? PROJECT.groups.flatMap(g => g.documents) : []; }
function sheetTabs() {   // the bottom bar of a schematic: the project's viewable documents, as the native tool's document tabs
  const box = $("tablist"); box.innerHTML = "";
  const docs = allDocs().filter(d => d.viewable && d.present).sort((a, b) => (a.kind !== "schematic") - (b.kind !== "schematic") || natural(a.name, b.name));
  for (const d of docs) { const t = document.createElement("div"); t.className = "tab doc-tab" + (DOC && DOC.id === d.id ? " cur" : "");
    t.style.borderBottomColor = DOC && DOC.id === d.id ? (KIND_COLOR[d.kind] || "#888") : "transparent";
    t.innerHTML = `<span class="sw" style="background:${KIND_COLOR[d.kind] || "#888"}"></span><span>${esc(d.name)}</span>`; t.title = d.path; t.onclick = () => openDoc(d); box.appendChild(t); }
  $("cur").textContent = S ? `${S.sheet.style} sheet · ${S.comps.length} parts · ${S.nets.filter(n => n.name).length} nets` : "";
}
function docByFile(name) { const want = String(name).replace(/\\/g, "/").split("/").pop().toLowerCase(); return allDocs().find(d => d.name.toLowerCase() === want && d.viewable && d.present); }
async function crossProbe(ref, kind) {   // open the first document of `kind` that holds the part `ref`, and select it there
  const want = ref.toLowerCase(), generation = navigation;
  for (const d of allDocs().filter(x => x.kind === kind && x.viewable && x.present)) {
    let sc = null; try { sc = await sceneOf(d); } catch (e) { if (generation !== navigation) return false; continue; }
    if (generation !== navigation) return false; if (!sc) continue;
    const ok = sc.comps.some(c => c.ref.toLowerCase() === want || (c.group || "").toLowerCase() === want);
    if (ok) { const shown = await openDoc(d); if (!shown || shown !== navigation) return false; find(ref); return true; } }
  showInfo(`No ${kind === "pcb" ? "board" : "schematic"} of this project holds <b>${esc(ref)}</b>.`); return false;
}
function schDouble(X, Y) {
  const oi = schPick(X, Y); if (oi < 0) return; const o = S.objects[oi];
  if (o.k === "sheet" && o.file) { const d = docByFile(o.file); if (d) openDoc(d); else showInfo(`The sheet <b>${esc(o.file)}</b> is not a viewable document of this project.`); return; }
  const ci = o.comp; if (ci >= 0) { const c = S.comps[ci]; crossProbe(c.group || c.ref, "pcb"); }
}
function schFind(q) {
  const ql = q.toLowerCase(); let ci = S.comps.findIndex(c => c.ref.toLowerCase() === ql);
  if (ci < 0) ci = S.comps.findIndex(c => (c.group || "").toLowerCase() === ql);
  if (ci >= 0) { selectComp(ci, true); return; }
  const ni = S.nets.findIndex(n => n.name && n.name.toLowerCase() === ql);
  if (ni >= 0) { selectNet(ni, true); return; }
  showInfo(`Nothing named <b>${esc(q)}</b> on this sheet.`);
}
function loadSch(scene, keepView) {
  st.itemInfo = false;
  const first = S === null || S !== scene && !keepView; if (!scene.mm) toMMsch(scene); S = scene;
  document.body.classList.add("sch"); if (st.mode3d) set3D(false);
  SCH.sel = -1; SCH.selNet = -1; SCH.selComp = -1; showInfo(null);
  cv.style.display = "block"; view.mirror = false;
  $("fname").textContent = S.meta.name; document.title = S.meta.name + " · Fenolite viewer";
  $("gen").textContent = S.meta.sha256 ? `SHA-256 ${S.meta.sha256.slice(0, 12)}` : "";
  const c = S.meta.counts || {};
  $("ovTitle").style.display = "none"; $("overlays").innerHTML = "";
  $("notes").innerHTML = (S.meta.notes || []).map(esc).join("<br>") + `<br>Read by the ${esc(S.meta.backend)} backend, evidence ${esc(S.meta.evidence)}.` +
    (c.kinds ? `<br>${c.items || 0} items: ${Object.entries(c.kinds).map(([k, n]) => `${n} ${esc(k)}`).join(" · ")}`   // a Draftsman sheet (c0180)
      : `<br>${c.components || 0} parts · ${c.pins || 0} pins · ${c.wires || 0} wires · ${c.nets || 0} nets · ${c.power_ports || 0} power ports · ${c.ports || 0} ports`);
  sheetTabs(); buildNav(); buildDiffList(); buildMessages(); buildVariants(); applyProjNet();
  if (first) { fitted = false; fit(); } else draw();
}

