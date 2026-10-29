// ================================================================== tables (c0190): a BOM document, an output job
const TBL = { sort: -1, up: true, q: "" };
function loadTable(scene) {
  S = scene; st.mode3d = false; document.body.classList.remove("sch", "lib"); document.body.classList.add("table");
  cv.style.display = "none"; glc.style.display = "none"; $("bar3d").style.display = "none";
  $("fname").textContent = scene.meta.name; document.title = scene.meta.name + " · Fenolite viewer";
  $("gen").textContent = scene.meta.sha256 ? `SHA-256 ${scene.meta.sha256.slice(0, 12)}` : "";
  $("notes").innerHTML = (scene.meta.notes || []).map(esc).join("<br>") + `<br>Read by the ${esc(scene.meta.backend || "?")} backend, evidence ${esc(scene.meta.evidence || "?")}.`;
  TBL.sort = -1; TBL.up = true; TBL.q = "";
  const box = $("tablewrap"); box.style.display = "block";
  box.innerHTML = `<div class="tblhead"><b>${esc(scene.title || scene.meta.name)}</b><input id="tblFilter" placeholder="Filter the rows…"><small id="tblCount"></small></div>` +
    `<table class="tbl"><thead><tr>${scene.columns.map((c, k) => `<th data-k="${k}" title="Sort">${esc(c)}</th>`).join("")}</tr></thead><tbody id="tblBody"></tbody></table>`;
  box.querySelectorAll("th").forEach(th => th.onclick = () => { const k = +th.dataset.k; TBL.up = TBL.sort === k ? !TBL.up : true; TBL.sort = k; renderRows(); });
  $("tblFilter").oninput = e => { TBL.q = e.target.value; renderRows(); };
  renderRows(); showInfo(null);
}
function renderRows() {
  const sc = S, q = TBL.q.trim().toLowerCase();
  const idx = sc.rows.map((r, i) => i).filter(i => !q || sc.rows[i].some(v => String(v).toLowerCase().includes(q)));
  if (TBL.sort >= 0) idx.sort((a, b) => natural(String(sc.rows[a][TBL.sort]), String(sc.rows[b][TBL.sort])) * (TBL.up ? 1 : -1));
  $("tablewrap").querySelectorAll("th").forEach(th => { const k = +th.dataset.k; th.textContent = sc.columns[k] + (k === TBL.sort ? (TBL.up ? " ▲" : " ▼") : ""); });
  $("tblBody").innerHTML = idx.map(i => { const go = ((sc.docs || [])[i] || []).length || ((sc.refs || [])[i] || []).length;
    const why = ((sc.docs || [])[i] || []).length ? "Open the document it binds" : "Select these parts on the board";
    return `<tr data-i="${i}"${go ? ` class="link" title="${why}"` : ""}>${sc.rows[i].map(v => `<td>${linkify(v)}</td>`).join("")}</tr>`; }).join("");
  $("tblBody").querySelectorAll("tr.link").forEach(tr => tr.onclick = ev => { if (ev.target.tagName !== "A") tableRow(+tr.dataset.i); });
  $("tblCount").textContent = `${idx.length} of ${sc.rows.length} rows`;
}
async function tableRow(i) {   // a bound document opens; a BOM line's parts are selected on the board with the filter (c0187)
  const docs = (S.docs || [])[i] || [], refs = (S.refs || [])[i] || [];
  if (docs.length) { const d = docs[0] === "[bom]" ? allDocs().find(x => x.kind === "bom") : docByFile(docs[0]); if (d) await openDoc(d); else showInfo(`${esc(docs[0])} is not a document of this project.`); return; }
  if (!refs.length) return;
  const d = allDocs().find(x => x.kind === "pcb" && x.viewable && x.present); if (!d) { showInfo("The project holds no board to show these parts on."); return; }
  const shown = await openDoc(d); if (!shown || shown !== navigation) return;
  const text = refs.map(r => `ref:${r}`).join(" | "); $("query").value = text; applyQuery(text, true);
}

