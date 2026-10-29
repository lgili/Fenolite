// ================================================================== project tree (left panel)
const KIND_COLOR = { pcb: "#3fb950", schematic: "#d29922", "schematic-library": "#a371f7", "pcb-library": "#58a6ff", "integrated-library": "#58a6ff", "output-job": "#8b949e", rules: "#8b949e",
  stackup: "#8b949e", project: "#8b949e", "library-table": "#8b949e", draftsman: "#db61a2", other: "#6e7681" };
function buildTree() {
  const box = $("tree"); box.innerHTML = "";
  if (!PROJECT) return;
  const head = document.createElement("div"); head.className = "proj"; head.textContent = PROJECT.project_file || PROJECT.name; head.title = `${PROJECT.source} project`; box.appendChild(head);
  for (const g of PROJECT.groups) {
    const gh = document.createElement("div"); gh.className = "grp"; gh.textContent = g.name; box.appendChild(gh);
    const list = document.createElement("div"); box.appendChild(list);
    gh.onclick = () => { gh.classList.toggle("closed"); list.style.display = gh.classList.contains("closed") ? "none" : "block"; };
    for (const d of g.documents) {
      const row = document.createElement("div"); row.className = "doc" + (DOC && DOC.id === d.id ? " sel" : "") + (d.present ? "" : " missing");
      row.title = `${d.path} · ${d.kind}${d.viewable ? "" : " (no viewer yet)"}`;
      row.innerHTML = `<span class="ic" style="background:${KIND_COLOR[d.kind] || KIND_COLOR.other}"></span>${esc(d.name)}`;
      row.onclick = () => { openDoc(d); setSidebar(false); }; list.appendChild(row);
    }
  }
}
function docCard(d) {
  REVIEW.doc = null; buildProjectReview();
  $("doccard").style.display = "flex"; $("tablewrap").style.display = "none"; cv.style.display = "none"; glc.style.display = "none";
  $("doctext").innerHTML = `<b style="color:#fff">${esc(d.name)}</b><br>Kind: ${esc(d.kind)}<br>Path: ${esc(d.path)}<br>Size: ${d.size == null ? "—" : d.size + " bytes"}<br>` +
    (d.present ? "" : "<br>The file is not in the project folder.<br>") + (d.viewable ? "" : "<br>Fenolite has no viewer for this kind of document yet.");
}
async function sceneOf(d) {
  if (SCENES.has(d.id)) return SCENES.get(d.id);
  const read = (SCENE_READS.get(d.id) || 0) + 1; SCENE_READS.set(d.id, read);
  if (RAW.has(d.id)) { const raw = RAW.get(d.id), sc = toUnits(await unpackScene(raw));
    if (SCENE_READS.get(d.id) === read && RAW.get(d.id) === raw) { RAW.delete(d.id); SCENES.set(d.id, sc); } return sc; }
  if (!LIVE) return null;
  const r = await fetch(`scene/${encodeURIComponent(d.id)}.json`, { cache: "no-store" }); if (!r.ok) throw new Error(await r.text());
  const sc = toUnits(await r.json()); if (SCENE_READS.get(d.id) === read) SCENES.set(d.id, sc); return sc;
}
function invalidateScene(id) {
  SCENES.delete(id); SCENE_READS.set(id, (SCENE_READS.get(id) || 0) + 1);
}
async function openDoc(d, keepView) {
  // A successful token lets callers verify ownership again after awaiting this function.
  const generation = ++navigation;
  if (!DOC || DOC.id !== d.id) { st.version = null; if (LIB) { LIB = null; document.body.classList.remove("lib"); } }
  DOC = d; buildTree(); showInfo(null);
  if (!keepView) { $("fname").textContent = d.name; document.title = d.name + " · Fenolite viewer"; }
  if (!d.viewable || !d.present) { docCard(d); return 0; }
  if (!keepView) { docCard(d); $("doctext").innerHTML += "<br><br>Reading…"; }
  loadingNavigation = generation;
  let sc; try { sc = await sceneOf(d); } catch (e) {
    if (generation === navigation) { docCard(d); $("doctext").innerHTML += `<br><br>Could not read it: ${esc(e.message)}`; } return 0;
  } finally { if (loadingNavigation === generation) loadingNavigation = 0; }
  if (generation !== navigation) return 0;
  if (!sc) { docCard(d); return 0; }
  $("doccard").style.display = "none";
  loadScene(sc, keepView); return generation;
}

