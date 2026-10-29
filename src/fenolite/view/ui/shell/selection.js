const SELECTION_VIEWS = [];
let SEL_KEY = "";
function selectionState() {
const out = { doc: DOC ? DOC.id : null, net: null, comp: null, finding: null };
if (!S) return out;
if (LIB && LIBSEL >= 0) out.item = LIB.items[LIBSEL].name;
if (S.kind === "table") { out.row = TBL.selected; return out; }
if (isSch()) {
if (SCH.selNet >= 0 && S.nets && S.nets[SCH.selNet]) { const n = S.nets[SCH.selNet]; out.net = n.project || n.name; }
if (SCH.selComp >= 0 && S.comps && S.comps[SCH.selComp]) out.comp = S.comps[SCH.selComp].ref;
} else {
if (st.selNet >= 0 && S.nets) out.net = S.nets[st.selNet] || null;
if (st.selComp >= 0 && S.comps && S.comps[st.selComp]) out.comp = S.comps[st.selComp].ref;
}
if (st.selFinding >= 0) out.finding = "check:" + st.selFinding;
else if (st.selMessage) out.finding = st.selMessage;
else if (isSch() && SCH.sel >= 0) out.object = SCH.sel;
return out;
}
function selectionHash() { const s = selectionState(); return JSON.stringify([s.doc, s.net, s.comp]); }
function selectionChanged() {
const s = selectionState(), key = JSON.stringify(s); if (key === SEL_KEY) return; SEL_KEY = key;
for (const view of SELECTION_VIEWS) try { view(s); } catch (e) { console.error(e); }
}
function announce(text) { const a = $("announce"); if (a && a.textContent !== text) a.textContent = text; }
SELECTION_VIEWS.push(s => announce(s.net ? `Selected net ${s.net}` : s.comp ? `Selected part ${s.comp}` : s.finding ? "Selected a finding" : s.item ? `Selected item ${s.item}` : s.row >= 0 ? `Selected row ${s.row + 1}` : "Nothing selected"));
function selectNetByName(name) {
if (!S || !name) return false;
if (isSch()) { const i = S.nets.findIndex(n => (n.project || n.name) === name || n.name === name); if (i < 0) return false; selectNet(i, true); return true; }
if (!S.nets || LIB) return false; const i = S.nets.indexOf(name); if (i < 0) return false; selectNetAt(i); return true;
}
function findingNet(x) {
if (!S || !S.nets || isSch()) return -1;
if (x.net) { const i = S.nets.indexOf(x.net); if (i >= 0) return i; }
for (const w of [x.object, ...String(x.where || "").split(/\s+/)]) { if (!w) continue; const i = S.nets.indexOf(String(w)); if (i >= 0) return i; }
return -1;
}
