let LIB = null, LIBSEL = -1, LIBQ = "";
function toUnits(sc) {
if (sc.kind === "table") return sc;
if (sc.kind === "library") { for (const it of sc.items) if (it.scene) toUnits(it.scene); return sc; }
return sc.kind === "schematic" ? toMMsch(sc) : toMM(sc);
}
function itemNote(it) {
if (it.copper_nm) { const b = it.copper_nm; return `${it.pads} pads · ${fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)}`; }
return it.pins != null ? `${it.pins} pins` : "";
}
function buildLibList() {
const box = $("libList"); box.innerHTML = ""; if (!LIB) return; const q = LIBQ.trim().toLowerCase();
$("libTitle").textContent = `${LIB.lib === "pcb" ? "Footprints" : LIB.lib === "drawing" ? "Sheets" : "Symbols"} (${LIB.items.length})`;
LIB.items.forEach((it, i) => { if (q && !it.name.toLowerCase().includes(q) && !(it.description || "").toLowerCase().includes(q)) return;
const d = document.createElement("div"); d.className = "navi" + (i === LIBSEL ? " sel" : ""); d.title = it.description || it.name;
d.innerHTML = `${esc(it.name)} <small>${esc(itemNote(it))}</small>`; d.onclick = () => openItem(i); box.appendChild(d); });
}
function itemInfo(it) {
const rows = [...it.info];
if (it.copper_nm) { const b = it.copper_nm; rows.push(["Copper extent", fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)]); }
if (it.courtyard_nm) { const b = it.courtyard_nm; rows.push(["Courtyard", fmtPair((b[2] - b[0]) / 1e6, (b[3] - b[1]) / 1e6)]); }
const title = `<b>Properties</b> · ${LIB.lib === "pcb" ? "Footprint" : LIB.lib === "drawing" ? "Sheet" : "Symbol"}`;
const table = rows.length ? `<table>${rows.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</table>` : "";
return it.lib_id ? `<details><summary>${title} · ${esc(it.evidence || "INFERRED")}</summary>${table}</details>` : title + table;
}
function openItem(i, keepView) {
LIBSEL = i; const it = LIB.items[i]; buildLibList();
if (!it.scene) { showInfo(`<b>${esc(it.name)}</b> could not be drawn; see the notes.`); return; }
if (it.scene.kind === "schematic") loadSch(it.scene, keepView); else loadBoard(it.scene, keepView);
document.body.classList.add("lib"); $("fname").textContent = `${LIB.meta.name} › ${it.name}`;
showInfo(itemInfo(it)); st.itemInfo = true;
}
function loadLibrary(scene, keepView) {
const prev = LIB && LIBSEL >= 0 ? LIB.items[LIBSEL].name : null; LIB = scene;
document.body.classList.add("lib");
let i = prev ? scene.items.findIndex(it => it.name === prev) : -1; if (i < 0) i = scene.items.findIndex(it => it.scene); if (i < 0) i = 0;
if (!scene.items.length) { LIBSEL = -1; buildLibList(); showInfo("This library holds no item."); return; }
openItem(i, keepView && prev !== null);
if (scene.meta.notes && scene.meta.notes.length) $("notes").innerHTML += "<br>" + scene.meta.notes.map(esc).join("<br>");
}
$("libFilter").addEventListener("input", e => { LIBQ = e.target.value; buildLibList(); });
function setUnit(u) {
UNIT = u; $("bUnit").textContent = u; try { localStorage.setItem("fenolite.view.unit", u); } catch (e) {  }
if (!S) return;
if (LIB && st.itemInfo && LIBSEL >= 0 && !st.lastHit && SCH.sel < 0) showInfo(itemInfo(LIB.items[LIBSEL]));
if (isSch()) { if (SCH.sel >= 0) schSelect(SCH.sel); else if (SCH.selNet >= 0) selectNet(SCH.selNet, false); }
else if (st.lastHit) select(st.lastHit, st.lastAt);
if (st.mouse) showCoord(st.mouse[0], st.mouse[1]);
buildLibList(); draw();
}
$("bUnit").onclick = () => setUnit(UNIT === "mm" ? "mil" : "mm");
$("bUnit").textContent = UNIT;
