// ================================================================== start: embedded data or the live server
async function start() {
  if (EMBED) { PROJECT = EMBED.project; for (const [id, sc] of Object.entries(EMBED.scenes)) RAW.set(id, sc); }   // decoded when opened
  else if (LIVE) { PROJECT = await (await fetch("project.json", { cache: "no-store" })).json(); if (PROJECT && PROJECT.settings) { Object.assign(SETTINGS, PROJECT.settings); startKeymap(); GIVEN_LAYOUT = SETTINGS.layout || null; setWorkspace(WS, true); } }
  document.body.classList.toggle("catalog", PROJECT?.source === "catalog");
  buildTree();
  loadMarks((EMBED && EMBED.marks) || (PROJECT && PROJECT.marks)); buildMarks();
  const docs = PROJECT ? PROJECT.groups.flatMap(g => g.documents) : [];
  const link = new URLSearchParams(location.hash.slice(1));   // c0189: a link opens where it was made
  const want = link.get("doc") || (EMBED && EMBED.open) || (PROJECT && PROJECT.open);
  const d = docs.find(x => x.id === want) || docs.find(x => x.viewable && x.present) || docs[0];
  const shown = d ? await openDoc(d) : 0;
  if (shown && shown === navigation) {
    if (link.get("doc") && DOC && DOC.id === link.get("doc")) applyLink(link);
    else applySelect((EMBED && EMBED.select) || (PROJECT && PROJECT.select));
    if (link.get("item") && LIB) { const i = LIB.items.findIndex(item => item.name === link.get("item")); if (i >= 0) openItem(i); }
  }
  linkReady = true;
  if (LIVE) setInterval(poll, 2000);
}
async function poll() {
  if (!DOC || !DOC.viewable || loadingNavigation === navigation) return;
  const doc = DOC, request = (POLLS.get(doc.id) || 0) + 1; let generation = navigation;
  POLLS.set(doc.id, request);
  const current = () => generation === navigation && DOC.id === doc.id && POLLS.get(doc.id) === request;
  try { const v = await (await fetch(`version/${encodeURIComponent(doc.id)}`, { cache: "no-store" })).json();
    if (!current()) return;
    $("live").textContent = v.error ? `error: ${v.error}` : v.building ? "reading…" : v.updated ? `live · updated ${v.updated}` : "live";
    if (v.building) return;
    if (v.version && v.version !== st.version) {
      invalidateScene(doc.id); const opening = openDoc(doc, true); generation = navigation;
      const shown = await opening; if (!shown || shown !== generation || !current()) return;
    }
    st.version = v.version || st.version;
  } catch (e) { if (current()) $("live").textContent = "server not reachable"; }
}
start();
