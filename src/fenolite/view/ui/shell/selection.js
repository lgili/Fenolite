// ================================================================== one selection (change c0245, decision 9, M3)
// The canvas, the panels, the layer tabs, the Messages panel, the status bar, the address and the windows of
// the same page all show one selection. Every way of selecting ends in a draw; the draw reads the state
// here, and when it changed, every view registered in SELECTION_VIEWS follows it.
const SELECTION_VIEWS = [];
let SEL_KEY = "";
function selectionState() {   // { doc, net, comp, finding }: names, so that two documents and two windows compare
  const out = { doc: DOC ? DOC.id : null, net: null, comp: null, finding: null };
  if (!S || S.kind === "table") return out;
  if (isSch()) {
    if (SCH.selNet >= 0 && S.nets && S.nets[SCH.selNet]) { const n = S.nets[SCH.selNet]; out.net = n.project || n.name; }
    if (SCH.selComp >= 0 && S.comps && S.comps[SCH.selComp]) out.comp = S.comps[SCH.selComp].ref;
  } else {
    if (st.selNet >= 0 && S.nets) out.net = S.nets[st.selNet] || null;
    if (st.selComp >= 0 && S.comps && S.comps[st.selComp]) out.comp = S.comps[st.selComp].ref;
  }
  if (st.selFinding >= 0) out.finding = "check:" + st.selFinding;
  else if (st.selMessage) out.finding = st.selMessage;
  return out;
}
function selectionHash() { const s = selectionState(); return JSON.stringify([s.doc, s.net, s.comp]); }
function selectionChanged() {
  const s = selectionState(), key = JSON.stringify(s); if (key === SEL_KEY) return; SEL_KEY = key;
  for (const view of SELECTION_VIEWS) try { view(s); } catch (e) { console.error(e); }
}
function announce(text) { const a = $("announce"); if (a && a.textContent !== text) a.textContent = text; }
SELECTION_VIEWS.push(s => announce(s.net ? `Selected net ${s.net}` : s.comp ? `Selected part ${s.comp}` : s.finding ? "Selected a finding" : "Nothing selected"));
function selectNetByName(name) {   // a net by its name, on a board or a sheet; false when the document has none
  if (!S || !name) return false;
  if (isSch()) { const i = S.nets.findIndex(n => (n.project || n.name) === name || n.name === name); if (i < 0) return false; selectNet(i, true); return true; }
  if (!S.nets || LIB) return false; const i = S.nets.indexOf(name); if (i < 0) return false; selectNetAt(i); return true;
}
function findingNet(x) {   // the net a finding names: its own field, else a word of its place or object that is a net
  if (!S || !S.nets || isSch()) return -1;
  if (x.net) { const i = S.nets.indexOf(x.net); if (i >= 0) return i; }
  for (const w of [x.object, ...String(x.where || "").split(/\s+/)]) { if (!w) continue; const i = S.nets.indexOf(String(w)); if (i >= 0) return i; }
  return -1;
}
