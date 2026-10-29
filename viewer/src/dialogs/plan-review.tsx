// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The plan review of c0271, a Preact dialog (change c0272, decision 10): one modal `#planDialog` whose body and
// buttons follow the phase of the action: planning (the dry run or the write is running), plan (the files, the
// issues, the evidence and Confirm), receipt, changed (FEN-4002: review again) and error.
import * as preact from "preact";
import { ACTS, actAgain, actCancel, actConfirm, actPreviewOff, actUndo } from "../actions/actions";
import { $ } from "../core/dom";

const PLAN_TITLES = { planning: "Planning", plan: "Review the plan", receipt: "Written", changed: "The file changed", error: "Not planned" };
const actShort = h => h ? `${String(h).slice(0, 12)}…` : "new file";
export function PlanIssues({ issues }: { issues: any[] }) {
  if (!issues.length) return <p class="notes">No issue reported.</p>;
  const order = { error: 0, warning: 1, info: 2 };
  return <ul class="planIssues">{[...issues].sort((a, b) => (order[a.severity] ?? 3) - (order[b.severity] ?? 3)).map(x =>
    <li class={x.severity}>{`${x.severity}: ${x.code} — ${x.message}`}</li>)}</ul>;
}
function PlanFiles({ writes }: { writes: any[] }) {
  return <table class="planFiles"><thead><tr><th>Writes</th><th>Kind</th><th>Bytes</th><th>New SHA-256</th><th>Replaces</th></tr></thead>
    <tbody>{writes.map(w => <tr><td>{String(w.path)}</td><td>{w.kind || ""}</td><td>{String(w.bytes)}</td>
      <td title={String(w.sha256)}>{actShort(w.sha256)}</td><td title={w.replaces || ""}>{actShort(w.replaces)}</td></tr>)}</tbody></table>;
}
function PlanPlan({ job }: { job: any }) {   // the body of a finished dry run
  const plan = job.plan;
  if (!plan) return <><p class="notes">The command planned no write.</p><PlanIssues issues={job.envelope?.issues || []} /></>;
  const q = ACTS.request || {}, note = ACTS.offer?.[job.action]?.note;
  const lead = q.undo ? `Puts back the backups of write ${q.undo}; restore refuses if a written file changed since.`
    : note ? note[0].toUpperCase() + note.slice(1) + (q.options?.reason ? `, with the reason “${q.options.reason}”.` : ".") : null;
  const evidence = plan.evidence ? plan.evidence.level + (plan.evidence.oracle ? ` (${plan.evidence.oracle})` : "") : "UNKNOWN";
  return <>
    {lead ? <p>{lead}</p> : null}
    <PlanFiles writes={plan.writes} />
    <PlanIssues issues={plan.issues} />
    <p class="notes">{`Evidence: ${evidence}`}</p>
    {job.preview ? <p class="notes">{`On the board: ${job.preview.changes.length} change(s) — added in green, removed in magenta, moved parts as arrows; listed under Changes.`}</p>
      : job.preview_note ? <p class="notes">{job.preview_note}</p> : null}
    {plan.refused ? <p class="planError">{plan.refused}</p> : null}
    {!plan.confirmable && !plan.refused ? <p class="planError">An error finding plans no write: Confirm is disabled.</p> : null}
  </>;
}
function PlanReceipt({ job }: { job: any }) {
  const r = job.receipt || {};
  return <>
    <p>{`Receipt ${r.id || "?"}: the plan was written; the document is read again.`}</p>
    <table class="planFiles"><thead><tr><th>Written</th><th>SHA-256</th></tr></thead>
      <tbody>{(r.written || []).map(w => <tr><td>{String(w.path)}</td><td title={String(w.sha256)}>{actShort(w.sha256)}</td></tr>)}</tbody></table>
    <p class="notes">{(r.backup || []).length ? `Backups kept: ${r.backup.join(", ")}` : "No backup was needed (new files only)."}</p>
  </>;
}
export function PlanBody({ view }: { view: any }) {
  if (view.phase === "planning") return <p class="notes" id="planStatus">{view.status || "Running the dry run; nothing is written."}</p>;
  if (view.phase === "error") return <p class="planError">{view.message}</p>;
  if (view.phase === "changed") return <><p class="planError">{view.message}</p><p class="notes">{view.hint || "The file changed since the review."}</p></>;
  if (view.phase === "plan") return <PlanPlan job={view.job} />;
  if (view.phase === "receipt") return <PlanReceipt job={view.job} />;
  return null;
}
export function PlanFoot({ view }: { view: any }) {
  if (view.phase === "planning") return <button onClick={actCancel}>Cancel</button>;
  if (view.phase === "error") return <button onClick={actClose}>Close</button>;
  if (view.phase === "changed") return <><button class="primary" onClick={actAgain}>Review again</button><button onClick={actClose}>Close</button></>;
  if (view.phase === "plan") {
    const plan = view.job.plan;
    if (!plan) return <button onClick={actClose}>Close</button>;
    return <><button class="primary" id="planConfirm" disabled={!plan.confirmable} onClick={() => actConfirm(view.job.job)}>Confirm and write</button>
      <button onClick={actClose}>Cancel</button></>;
  }
  if (view.phase === "receipt") {
    const r = view.job.receipt || {};
    return <>{r.id && view.job.action !== "undo" ? <button onClick={() => actUndo(r.id)}>Undo…</button> : null}
      <button class="primary" onClick={actClose}>Close</button></>;
  }
  return null;
}
export function actRender(view) {   // the dialog's title, body and buttons for a view; a new phase renders afresh
  $("planTitle").textContent = PLAN_TITLES[view.phase] + ` · ${view.title}`;
  preact.render(<PlanBody key={view.phase} view={view} />, $("planBody"));
  preact.render(<PlanFoot key={view.phase} view={view} />, $("planFoot"));
}
export function actDialog(view) {
  const dlg = $("planDialog"); ACTS.open = view;
  actRender(view);
  if (!dlg.open) dlg.showModal();
  const foot = $("planFoot");
  (foot.querySelector("button.primary:not([disabled])") || foot.querySelector("button")).focus();
}
export function actClose() { actPreviewOff(); const dlg = $("planDialog"); if (dlg.open) dlg.close(); ACTS.open = null; }
$("planDialog").addEventListener("cancel", e => { e.preventDefault(); actClose(); });
