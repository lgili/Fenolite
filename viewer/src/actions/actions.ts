// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== writing actions (c0303)
// Only a page served with --allow-actions offers them (GET /actions). Every action is a dry run first: the
// plan dialog names the files, the issues and the evidence, and draws the staged board's changes over the
// current one. Confirm writes exactly that plan (--confirm --plan); the receipt follows, then the document is
// read again. Undo plans `restore` on a receipt of this session, reviewed and confirmed the same way.
// The client, the action forms of the Project review and Waive live here; the dialog is dialogs/plan-review,
// the list of this session's writes panels/receipts.
import { draw } from "../board/draw";
import { diffToMM } from "../board/scene";
import { invalidateScene, openDoc } from "../core/documents";
import { $, esc } from "../core/dom";
import { PREVIEW_MODE } from "../core/env";
import { DOC, S, st } from "../core/state";
import { MIL_MM, UNIT } from "../core/units";
import { actClose, actDialog, actRender } from "../dialogs/plan-review";
import { buildDiffList } from "../panels/changes";
import { buildReceipts } from "../panels/receipts";
import { markStale, runCall, RUNS } from "../review/runs";
import { refreshInspector } from "../panels/inspector";
export const ACTS = { failed:false, enabled:false, token:"", offer:null, doc:null, reason:"", receipts:[], job:null, timer:0, request:null, saved:null, open:null };
export const ACT_FORMS = ["fill", "tidy", "silk", "testpoints", "export", "bom"];
function actHeaders() { return { "Content-Type": "application/json", "X-Fenolite-Action": "1", "X-Fenolite-Token": ACTS.token }; }
export async function actionsLoad() {
  if (!LIVE || PREVIEW_MODE || !DOC) return;
  const doc = DOC.id; ACTS.failed = false;
  try { const r = await fetch(`actions?doc=${encodeURIComponent(doc)}`, { cache: "no-store", headers: { "X-Fenolite-Action": "1" } });
    const data = await r.json(); if (!DOC || DOC.id !== doc) return;
    ACTS.enabled = !!data.enabled; ACTS.token = data.token || ""; ACTS.offer = data.actions || {}; ACTS.receipts = data.receipts || [];
    ACTS.reason = data.reason || ""; ACTS.doc = doc;
  } catch (e) { ACTS.enabled = false; ACTS.doc = doc; ACTS.failed = true; }   // c0301: the Project review asks again when it opens
  buildActionPanel(); refreshInspector();   // c0301: the inspector offers the actions that apply
}
function actLen(mm) { return UNIT === "mil" ? `${(mm / MIL_MM).toFixed(2)}mil` : `${mm.toFixed(3)}mm`; }
function actField(key, o, value) {   // one typed field of an action form, built from the server's option table
  const id = `act_${key}`, label = esc(o.label || key);
  if (o.type === "boolean") return `<label class="runOpt"><input type="checkbox" data-opt="${key}" ${(value ?? o.default) ? "checked" : ""}> ${label}</label>`;
  if (o.type === "choice") return `<label class="actField">${label}<select data-opt="${key}"><option value="">default</option>${o.choices.map(c => `<option ${c === value ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>`;
  if (o.type === "kinds") return `<div class="runGrid">${o.choices.map(c => `<label><input type="checkbox" data-kind="${key}" value="${esc(c)}" ${(o.default || []).includes(c) ? "checked" : ""}> ${esc(c)}</label>`).join("")}</div>`;
  const hint = o.type === "length" ? (UNIT === "mil" ? "e.g. 100mil" : "e.g. 2.54mm") : o.type === "angle" ? "degrees" : "";
  return `<label class="actField">${label}<input id="${id}" data-opt="${key}" value="${esc(value ?? (typeof o.default === "string" ? o.default : ""))}" placeholder="${hint}" ${o.required ? "required" : ""}></label>`;
}
function actOptions(box) {   // the typed values of a form: empty fields are left to the server's defaults
  const out = {};
  for (const el of box.querySelectorAll("[data-opt]") as NodeListOf<HTMLInputElement>) { const k = el.dataset.opt;
    if (el.type === "checkbox") out[k] = el.checked; else if (el.value.trim() !== "") out[k] = k === "refs" ? el.value.split(",").map(s => s.trim()).filter(Boolean) : el.value.trim(); }
  const kinds = {}; for (const el of box.querySelectorAll("[data-kind]:checked") as NodeListOf<HTMLInputElement>) (kinds[el.dataset.kind] = kinds[el.dataset.kind] || []).push(el.value);
  return { ...out, ...kinds };
}
function actForm(name, values?) {   // a details box: the options of one action and its Plan button
  const a = ACTS.offer[name], d = document.createElement("details"); d.className = "actBox"; d.dataset.action = name;
  const fields = Object.entries(a.options).map(([k, o]) => actField(k, o, values && values[k])).join("");
  d.innerHTML = `<summary>${esc(a.title)}</summary>${a.note ? `<p class="notes">${esc(a.note)}</p>` : ""}${fields}<div class="runRow"><button class="actPlan">Review plan…</button></div>`;
  const plan = d.querySelector(".actPlan") as HTMLButtonElement;
  plan.onclick = () => actPlan(name, actOptions(d));
  if (!a.available) { plan.disabled = true; d.title = a.why || ""; }
  if (name === "move") actNudge(d);
  return d;
}
function actNudge(box) {   // arrow keys in the move form shift the part by one step of the page unit
  box.addEventListener("keydown", e => {
    const map = { ArrowLeft:["x", -1], ArrowRight:["x", 1], ArrowUp:["y", -1], ArrowDown:["y", 1] }, m = map[e.key];
    if (!m || !(e.target instanceof HTMLInputElement) || !["x", "y"].includes(e.target.dataset.opt)) return;
    const f = box.querySelector(`[data-opt="${m[0]}"]`), v = /^(-?\d+(?:\.\d+)?)(mm|mil|um)$/.exec(f.value.trim()); if (!v) return;
    e.preventDefault(); const step = v[2] === "mil" ? 1 : v[2] === "um" ? 100 : 0.1;
    f.value = `${(+v[1] + m[1] * step * (e.shiftKey ? 10 : 1)).toFixed(v[2] === "mm" ? 3 : 1)}${v[2]}`;
  });
}
export function buildActionPanel(retry = false) {   // retry: the Project review was opened, a failed read of the offer is tried again
  const panel = $("actionPanel"); if (!panel) return;
  if (LIVE && DOC && (ACTS.doc !== DOC.id || (retry && ACTS.failed))) { ACTS.doc = DOC.id; actionsLoad(); }
  panel.innerHTML = ""; panel.hidden = !ACTS.enabled || !DOC || ACTS.doc !== DOC.id; if (panel.hidden) return;
  const head = document.createElement("h3"); head.textContent = "Actions (writes files)"; panel.appendChild(head);
  const unavailable: any = Object.values(ACTS.offer).find((a: any) => !a.available);
  const note = document.createElement("p"); note.className = "notes";
  note.textContent = unavailable ? unavailable.why : "Each action shows its plan on the board first; nothing is written until you confirm. Every write keeps a backup and can be undone.";
  panel.appendChild(note); if (unavailable) return;
  for (const name of ACT_FORMS) if (ACTS.offer[name]) panel.appendChild(actForm(name));
  const sel = st.selComp >= 0 && S && S.comps ? S.comps[st.selComp] : null;
  if (ACTS.offer.move && S && S.comps) panel.appendChild(actForm("move", sel ? { ref: sel.ref, x: actLen(sel.x), y: actLen(sel.y), rot: String(sel.rotation ?? "") } : {}));
  if (ACTS.offer.shift) panel.appendChild(actForm("shift", { refs: sel ? sel.ref : "", dx: actLen(1), dy: actLen(0) }));
  if (ACTS.offer.turn) panel.appendChild(actForm("turn", sel ? { refs: sel.ref, about_x: actLen(sel.x), about_y: actLen(sel.y), angle: "90" } : {}));
  buildReceipts(panel, ACTS.receipts);
  for (const b of panel.querySelectorAll("button")) if (ACTS.job) b.disabled = true;
}
export function waiveBlocked() {   // c0303, fix of 2026-10-29: why Waive is not offered on the current results, or ""
  const b = S && S.project_review?.binding, stale = DOC && RUNS.stale.get(DOC.id);
  if (stale) return stale.text;
  if (b && (!b.matched || (b.sha256 && S.meta?.sha256 && b.sha256 !== S.meta.sha256)))
    return "This finding comes from a check of an earlier revision of the file, so its index may name another violation now. Run the checks again before waiving it.";
  return "";
}
export function actWaiveButton(x, detail) {   // Waive finding, for a finding of KiCad's DRC listed in the review
  if (!ACTS.enabled || x.checkIndex == null || x.stage !== "drc.kicad" || !ACTS.offer?.waive?.available) return;
  const why = waiveBlocked();
  if (why) { const p = document.createElement("p"); p.className = "actWhy"; p.id = "actWaiveWhy"; p.textContent = `Waive is not offered. ${why}`; detail.appendChild(p); return; }
  const box = document.createElement("div"); box.className = "actWaive";
  box.innerHTML = '<label class="actField">Reason for the waiver (stored in the project)<input id="actReason" maxlength="300" placeholder="Accepted by design: …"></label><button id="actWaive">Waive finding…</button>';
  const reasonField = box.querySelector("#actReason") as HTMLInputElement;
  (box.querySelector("#actWaive") as HTMLButtonElement).onclick = () => { const reason = reasonField.value.trim();
    if (!reason) { reasonField.focus(); return; } actPlan("waive", { finding: x.checkIndex, reason }); };
  detail.appendChild(box);
}
async function actPost(path, body) {
  const r = await fetch(path, { method: "POST", headers: actHeaders(), body: JSON.stringify(body) });
  let data: any = {}; try { data = await r.json(); } catch (e) { data = {}; } return { ok: r.ok, status: r.status, data };
}
export async function actPlan(action, options) {
  if (!ACTS.enabled || ACTS.job || !DOC) return;
  ACTS.request = { action, options, doc: DOC.id };
  actDialog({ phase: "planning", title: ACTS.offer[action]?.title || action });
  const r = await actPost("action/plan", { action, doc: DOC.id, options });
  if (!r.ok) return actDialog({ phase: "error", title: ACTS.offer[action]?.title || action, message: r.data.error || `the server answered ${r.status}` });
  actFollow(r.data.job, "plan");
}
export async function actUndo(receipt) {
  if (!ACTS.enabled || ACTS.job) return;
  ACTS.request = { undo: receipt };
  actDialog({ phase: "planning", title: "Undo a write" });
  const r = await actPost("action/undo", { receipt });
  if (!r.ok) return actDialog({ phase: "error", title: "Undo a write", message: r.data.error || `the server answered ${r.status}` });
  actFollow(r.data.job, "plan");
}
export async function actConfirm(job) {   // writes the reviewed plan; the dialog shows the write's progress
  actDialog({ phase: "planning", title: ACTS.open?.title || "Action", status: "Writing the reviewed plan…" });
  const r = await actPost("action/confirm", { job });
  if (!r.ok) { actPreviewOff(); return actDialog({ phase: "error", title: "Action", message: r.data.error || `the server answered ${r.status}` }); }
  actFollow(r.data.job, "confirm");
}
export function actAgain() { const q = ACTS.request; if (!q) return actClose(); if (q.undo) actUndo(q.undo); else actPlan(q.action, q.options); }
export async function actCancel() {   // Cancel while planning: closes the dialog, then stops the job
  const j = ACTS.job; actClose(); if (j) await runCall(`run/${encodeURIComponent(j.job)}/cancel`, {});
}
function actFollow(job, phase) {   // poll a job of the dialog until it ends
  ACTS.job = { job, phase }; buildActionPanel(); clearTimeout(ACTS.timer);
  const step = async () => {
    const mine = ACTS.job; if (!mine) return;
    let r; try { r = await runCall(`run/${encodeURIComponent(mine.job)}`); } catch (e) { r = { ok:false, data:{} }; }
    if (ACTS.job !== mine) return;
    if (r.ok && r.data.state === "running") { actProgress(r.data); ACTS.timer = setTimeout(step, 400); return; }
    ACTS.job = null; buildActionPanel();
    if (!ACTS.open) return;   // the dialog was closed: a cancelled job says nothing more
    if (!r.ok) return actDialog({ phase: "error", title: "Action", message: "The server no longer knows this job." });
    if (mine.phase === "plan") actPlanned(r.data); else actWritten(r.data);
  };
  ACTS.timer = setTimeout(step, 300);
}
function actProgress(job) {   // the running job's last step, in the dialog's status line
  if (!ACTS.open || ACTS.open.phase !== "planning") return; const last = (job.progress || []).slice(-1)[0];
  ACTS.open = { ...ACTS.open, status: `${job.command} running · ${last ? [last.step, last.detail].filter(Boolean).join(" · ") : "starting"} · ${Number(job.elapsed || 0).toFixed(0)} s` };
  actRender(ACTS.open);
}
function actPreview(diff) {   // the staged board's changes, drawn as the --compare overlay of the current scene
  if (!S || S.kind != null) return;
  if (ACTS.saved === null) ACTS.saved = { diff: S.diff || null, on: st.diff };
  if (diff) { const holder = { diff: JSON.parse(JSON.stringify(diff)) }; diffToMM(holder); S.diff = holder.diff; S.diff.old = { name: "the plan (staged bytes)" }; st.diff = true; }
  else S.diff = ACTS.saved.diff;
  buildDiffList(); draw();
}
export function actPreviewOff() { if (ACTS.saved && S) { S.diff = ACTS.saved.diff; st.diff = ACTS.saved.on; buildDiffList(); draw(); } ACTS.saved = null; }
function actPlanned(job) {
  const title = job.action === "undo" ? "Undo a write" : ACTS.offer[job.action]?.title || job.action;
  if (job.state !== "done") return actDialog({ phase: "error", title, message: actError(job) });
  actPreview(job.preview || null);
  actDialog({ phase: "plan", title, job });
}
function actWritten(job) {
  const title = job.action === "undo" ? "Undo a write" : ACTS.offer[job.action]?.title || job.action;
  actPreviewOff();
  if (job.review_again) return actDialog({ phase: "changed", title, message: actError(job), hint: job.hint });
  if (job.state !== "done") return actDialog({ phase: "error", title, message: actError(job) });
  actDialog({ phase: "receipt", title, job });
  const written = (job.receipt?.written || []).map(w => String(w.path)), own = DOC && DOC.id === job.doc ? DOC.name.toLowerCase() : "";
  const others = written.filter(p => p.replace(/\\/g, "/").split("/").pop().toLowerCase() !== own);
  if (job.action !== "undo" && others.length && (job.action === "waive" || others.some(p => /\.(kicad_pro|kicad_dru)$/i.test(p))))
    markStale(job.doc, `The checks predate this write: ${others.join(", ")} changed (${title.toLowerCase()}). Their results are stale until the checks run again.`);
  if (DOC && DOC.id === job.doc) { invalidateScene(job.doc); openDoc(DOC, true); }
  actionsLoad();
}
function actError(job) { const e = job.error || {}; return `${job.command} ${job.state}${e.code ? ` (${e.code})` : ""}: ${e.message || "no reason given"}${e.hint ? `. ${e.hint}` : ""}`; }
window.FenoliteActions = { plan: actPlan, undo: actUndo, state: ACTS };   // for the toolbar, palette and inspector (c0300, c0301)
