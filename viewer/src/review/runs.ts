// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== run checks from the page (c0302)
// Only a live server with a runner offers runs (GET /runs); an exported page never asks. One job at a time:
// the strip shows its command, last progress record, elapsed time and Cancel; the results land on the scene of
// the job's document, and are drawn only while that document is the one shown (the navigation guard).
// The client and the run state live here; the strip is panels/run-strip, the Run controls panels/project-review.
import { draw } from "../board/draw";
import { PREVIEW_MODE } from "../core/env";
import { DOC, MM, PROJECT, S, SCENES } from "../core/state";
import { buildFindings } from "../panels/findings";
import { buildMessages } from "../panels/messages";
import { buildProjectReview } from "../panels/project-review";
import { runStrip } from "../panels/run-strip";
import { checkToMM } from "./check";
import { refreshInspector } from "../panels/inspector";
import { buildLayers } from "../panels/layers";
import { buildRoles } from "../panels/roles";
import { resetRoleCache } from "../roles/draw";
import { rolesToMM } from "../roles/roles";
export const RUNS = { enabled:false, offer:null, reason:"", job:null, timer:0, results:new Map(), message:null,
  last:new Map(), stale:new Map() };   // c0303 fix: the last run of each document, and the documents whose results a write made stale
export const CARD_STAGES = { connectivity:["parity", "netlist.assignment_compare"], erc:["erc.kicad"], drc:["drc.kicad"],
  clearance:["copper.clearance"], placement:["placement.rules"], fill:["zone.fill"], model:["model.validate"] };
export const RUN_HEADERS = { "Content-Type": "application/json", "X-Fenolite-Run": "1" };
export async function runCall(path, body?, headers?) {
  const r = await fetch(path, body === undefined ? { cache: "no-store" } : { method: "POST", headers: headers || RUN_HEADERS, body: JSON.stringify(body) });
  let data: any = {}; try { data = await r.json(); } catch (e) { data = {}; }
  return { ok: r.ok, status: r.status, data };
}
export function runAltium() { const name = (DOC && DOC.name || "").toLowerCase(); return PROJECT?.source === "altium" || /\.(pcbdoc|schdoc|prjpcb)$/.test(name); }
export function runStages() {   // the stages the server lets this document run
  const o = RUNS.offer?.commands?.check?.options?.stages; if (!o) return [];
  return runAltium() ? o.altium || [] : o.choices || [];
}
export async function runsInit() {
  if (!LIVE || PREVIEW_MODE) return;
  try { const r = await runCall("runs"); if (!r.ok) return; RUNS.enabled = !!r.data.enabled; RUNS.offer = r.data; RUNS.reason = r.data.reason || "";
    if (r.data.busy) { RUNS.job = r.data.busy; pollRun(); } } catch (e) { RUNS.enabled = false; }
  buildProjectReview(); runStrip();
}
export async function startRun(command, options) {
  if (!RUNS.enabled || RUNS.job || !DOC) return;
  RUNS.message = null; RUNS.last.set(DOC.id, { command, options });
  const r = await runCall("run", { command, doc: DOC.id, options });
  if (r.status === 409 && r.data.job) { RUNS.job = { job: r.data.job, command, doc: DOC.id, state: "running", progress: [], elapsed: 0 }; pollRun(); return; }
  if (!r.ok) { runSay("failed", r.data.error || `the server answered ${r.status}`); return; }
  RUNS.job = { job: r.data.job, command, doc: DOC.id, state: "running", progress: [], elapsed: 0 };
  runRefresh(); pollRun();
}
export function runRefresh() { buildProjectReview(); runStrip(); if (S && !S.kind) buildRoles(); }
export function runCancel() {   // asks the server to stop the running job; its final state arrives by polling
  const j = RUNS.job; if (!j) return null;
  j.cancelling = true; runStrip();
  return runCall(`run/${encodeURIComponent(j.job)}/cancel`, {});
}
function pollRun() {
  clearTimeout(RUNS.timer);
  RUNS.timer = setTimeout(async () => {
    const mine = RUNS.job; if (!mine) return;
    let r; try { r = await runCall(`run/${encodeURIComponent(mine.job)}`); } catch (e) { r = { ok:false, status:0, data:{} }; }
    if (RUNS.job !== mine) return;
    if (!r.ok) { RUNS.job = null; runSay("failed", "The server no longer knows this run."); runRefresh(); return; }
    if (r.data.state === "running") { RUNS.job = { ...mine, ...r.data }; runStrip(); pollRun(); return; }
    RUNS.job = null; runFinished(r.data); runRefresh();
  }, 500);
}
function runFinished(job) {
  if (job.state === "cancelled") return runSay("cancelled", `${job.command} was cancelled; nothing changed.`);
  if (job.state === "timeout") return runSay("cancelled", `${job.command} ran past the time limit and was stopped; nothing changed.`);
  if (job.state !== "done") {
    const e = job.error || {}, missing = job.exit === 6 ? " The stages that need kicad-cli could not run." : "";
    return runSay("failed", `${job.command} failed${e.code ? ` (${e.code})` : ""}: ${e.message || "no reason given"}${missing}`, e.hint);
  }
  RUNS.results.set(job.doc, { ...(RUNS.results.get(job.doc) || {}), [job.command]: job });
  if (job.command === "check") RUNS.stale.delete(job.doc);   // fresh results for the current files
  const sc = SCENES.get(job.doc); if (sc) runApply(sc, job);
  const n = (job.envelope?.issues || []).length;
  runSay("done", `${job.command} finished: exit ${job.exit}, ${n} finding${n === 1 ? "" : "s"}.` + (job.note ? ` ${job.note}` : "") + (DOC && DOC.id !== job.doc ? " Results kept for their document." : ""));
}
function runPoints(list) { const f = v => v * MM; for (const x of list) { if (x.at) x.at = x.at.map(f); if (x.box) x.box = x.box.map(f); } return list; }
function runApply(sc, job) {   // a finished run on the scene of its document; drawn only when that scene is shown
  const copy = v => JSON.parse(JSON.stringify(v));
  if (job.check) { sc.check = copy(job.check); checkToMM(sc); }
  if (job.review) sc.project_review = copy(job.review);
  if (job.overlays && sc.kind == null) {
    const items = copy(job.overlays); for (const o of items) { o.pts = o.pts.map(p => p.map(v => v * MM)); if (o.bbox) o.bbox = o.bbox.map(v => v * MM); }
    sc.overlays = (sc.overlays || []).filter(o => o.source !== "run:analyze").concat(items);
    const ids = new Set((job.groups || []).map(g => g.id));
    sc.meta.findings = (sc.meta.findings || []).filter(g => !ids.has(g.id)).concat(copy(job.groups || []));
  }
  if (job.findings) sc.run_findings = runPoints(copy(job.findings));
  if (job.command === "roles" && sc.kind == null) { sc.roles = job.roles ? copy(job.roles) : null; rolesToMM(sc); }   // c0305
  if (S === sc && DOC && DOC.id === job.doc) {
    if (sc.kind == null) { buildFindings(); if (job.command === "roles") { resetRoleCache(); buildRoles(); buildLayers(); refreshInspector(); } }
    buildMessages(); buildProjectReview(); draw();
  }
}
export function runReapply(scene) {   // a scene read again keeps the analyze, ready and compare results of this session
  const kept = DOC && RUNS.results.get(DOC.id); if (!kept || scene.runApplied) return; scene.runApplied = true;
  for (const command of ["analyze", "ready", "equivalent"]) if (kept[command]) runApply(scene, kept[command]);
}
export function runSay(kind, text, hint?, action?) { RUNS.message = { kind, text, hint, action }; runStrip(); }
// c0303, fix of 2026-10-29: a write of an action can change what the last checks judged (a waiver writes the
// project file, not the board, so the board's digest still matches). The results of that document are marked
// stale until a check runs again; the strip, the Project review and the inspector offer Run again.
export function markStale(doc, text) { RUNS.stale.set(doc, { text, at: new Date().toLocaleTimeString() }); runSay("stale", text, undefined, runAgainAction(doc)); runRefresh(); refreshInspector(); }
export function runAgainAction(doc) { return RUNS.enabled ? { label: "Run again", run: () => runAgain(doc) } : null; }
export function runAgain(doc?) {   // the document's last run, else every check
  const id = doc || (DOC && DOC.id); if (!id || !DOC || DOC.id !== id) return; const last = RUNS.last.get(id) || { command: "check", options: {} };
  startRun(last.command, last.options);
}
window.FenoliteRuns = { start: startRun, cancel: runCancel, state: RUNS };   // for the toolbar and palette commands (c0300)
