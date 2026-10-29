// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ---- review marks: kept by the server in the --marks file, else in this browser until downloaded
import * as preact from "preact";
import { draw } from "../board/draw";
import { allDocs, navigation, openDoc } from "../core/documents";
import { $, download, esc, showInfo } from "../core/dom";
import { selName } from "../core/links";
import { ctx, DOC, PROJECT, st, view } from "../core/state";
import { fit, worldTf } from "../core/viewport";
import { isSch } from "../sch/scene";
import { set3D } from "../three/view3d";
import { Icon } from "../ui/icons";
import { showSection } from "../ui/section";
import { Empty } from "../ui/states";
import { imodel, irow, isection } from "../inspect/model";
import { inspect } from "./inspector";
export let MARKS = [];
export const marksKey = () => "fenolite.view.marks:" + (PROJECT ? PROJECT.name : "");
export const serverMarks = () => LIVE && PROJECT && PROJECT.marks_file;
export function loadMarks(given) {
  MARKS = Array.isArray(given) ? given : [];
  if (!serverMarks()) try { const kept = JSON.parse(localStorage.getItem(marksKey()) || "null"); if (Array.isArray(kept)) { const ids = new Set(MARKS.map(m => m.id)); MARKS = MARKS.concat(kept.filter(m => !ids.has(m.id))); } } catch (e) { /* no storage */ }
}
export async function sendMark(body) {   // the server writes the file; an exported page keeps the marks here
  if (serverMarks()) {
    const r = await fetch("marks", { method: "POST", headers: { "Content-Type": "application/json", "X-Fenolite-Review": "1" }, body: JSON.stringify(body) });
    const reply = await r.json(); if (!r.ok) { showInfo(`Mark not saved: ${esc(reply.error || r.status)}`); return; } MARKS = reply.marks;
  } else {
    MARKS = MARKS.filter(m => m.id !== body.id); if (body.note !== null) MARKS.push(body);
    try { localStorage.setItem(marksKey(), JSON.stringify(MARKS)); } catch (e) { /* no storage */ }
  }
  buildMarks(); draw();
}
export function markClick(x, y) {
  const note = window.prompt("Note for this mark", ""); if (note === null) return;
  sendMark({ id: "m" + Date.now().toString(36), doc: DOC.name, x_nm: Math.round(x * 1e6), y_nm: Math.round(y * 1e6), note, select: selName(), created: new Date().toISOString() });
}
export function drawMarks() {
  if (!DOC || !MARKS.length) return; if (!isSch()) worldTf(); ctx.globalAlpha = 1;
  MARKS.forEach((m, i) => { if (m.doc !== DOC.name) return; const x = m.x_nm / 1e6, y = m.y_nm / 1e6, r = 7 / view.s;
    ctx.fillStyle = "#ffd400"; ctx.strokeStyle = "#000"; ctx.lineWidth = 1 / view.s;
    ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - r * 0.8, y - r * 1.6); ctx.arc(x, y - r * 2, r, Math.PI * 0.8, Math.PI * 0.2); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = "#000"; ctx.font = `600 ${(10 / view.s).toFixed(4)}px system-ui`; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillText(String(i + 1), x, y - r * 2);
    ctx.textAlign = "start"; ctx.textBaseline = "alphabetic"; });
}
async function openMark(m, i) {   // the mark's document, then its place; a newer navigation wins (c0235)
  const doc = allDocs().find(x => x.name === m.doc);
  if (doc && doc !== DOC) { const shown = await openDoc(doc); if (!shown || shown !== navigation) return; } if (st.mode3d) set3D(false);
  const x = m.x_nm / 1e6, y = m.y_nm / 1e6, e = isSch() ? 25 : 5; fit([x - e, y - e, x + e, y + e]);
  inspect(() => imodel("mark", `Mark ${i + 1}`, [isection("Review mark", [irow("Note", m.note || "(no note)"), irow("On", m.select), irow("Document", m.doc), irow("Created", m.created)])],
    { subtitle: serverMarks() ? "Kept in the marks file" : "Kept in this browser" }));
}
// A row keeps its click as the element's onclick (c0300): the navigation tests call it and await its promise.
export function MarksPanel({ marks }: { marks: any[] }) {
  return <>
    {marks.length ? marks.map((m, i) => <div key={m.id} class="navi mark" ref={el => { if (el) el.onclick = () => openMark(m, i); }}>
      <span class="markNo">{i + 1}</span><span class="markText">{m.note || "(no note)"}<small>{`${m.doc}${m.select ? " · " + m.select : ""}`}</small></span>
      <button type="button" class="tb icon ghost small" aria-label={`Delete mark ${i + 1}`} data-tip="Delete this mark"
        onClick={ev => { ev.stopPropagation(); if (window.confirm(`Delete mark ${i + 1}?`)) sendMark({ id: m.id, note: null }); }}><Icon name="x" /></button>
    </div>) : <Empty text="No marks yet. Press N, then click the drawing to drop one." icon="pin" />}
    {!serverMarks() ? <button type="button" class="tb wide" data-tip="Save them as a fenolite.review.v0 file for fenolite view --marks"
      onClick={() => download(JSON.stringify({ schema: "fenolite.review.v0", marks: MARKS }, null, 2) + "\n", "review.json", "application/json")}>
      <Icon name="download" /><span class="lbl">Download marks</span></button> : null}
  </>;
}
export function buildMarks() {
  showSection("marks", MARKS.length > 0 || !LIVE, MARKS.length, "Marks" + (serverMarks() ? "" : " · in this browser"));
  preact.render(<MarksPanel marks={MARKS} />, $("marksList"));
}
