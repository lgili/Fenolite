// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== project review: recorded evidence and a guided finding list (c0239)
import { actWaiveButton, buildActionPanel } from "../actions/actions";
import { $, esc, showInfo } from "../core/dom";
import { setSidebar } from "../core/input";
import { DOC, PROJECT, S, st } from "../core/state";
import { fit } from "../core/viewport";
import { selectFinding } from "../review/check";
import { CARD_STAGES, runAltium, RUNS, runSay, runStages, startRun } from "../review/runs";
export const REVIEW = { doc: null, selected: -1, items: [], matches: [] };
export const REVIEW_STATE = { "not-run": "Not run", passed: "Passed", failed: "Failed", limited: "Limited" };
export function setProjectReview(open) {
  $("projectReview").hidden = !open; $("bProjectReview").setAttribute("aria-expanded", String(open));
  if (open) { setSidebar(false); buildProjectReview(); $("reviewClose").focus(); }
  else (matchMedia("(max-width:760px)").matches ? $("bSidebar") : $("bProjectReview")).focus();
}
$("bProjectReview").onclick = () => setProjectReview($("projectReview").hidden);
$("reviewClose").onclick = () => setProjectReview(false);
$("reviewJump").onclick = () => { $("reviewFindingHeading").scrollIntoView({block:"start"}); $("reviewFindingHeading").focus(); };
$("projectReview").addEventListener("keydown", e => {
  if (e.key === "Escape" && !e.isComposing) { e.preventDefault(); e.stopPropagation(); setProjectReview(false); }
});
export function buildProjectReview() {
  if ($("projectReview").hidden) return;
  const ready = S && DOC && REVIEW.doc === DOC.id;
  const data = ready && S.project_review;
  const box = $("reviewCards"); box.innerHTML = "";
  $("reviewScope").textContent = ready
    ? `${DOC.name}. ${data?.note || "No validation report was supplied. Reading a drawing is not an electrical check."}`
    : "This document has not been read. Select a viewable document to review it.";
  if (data?.binding && !data.binding.matched) $("reviewScope").textContent += " " + data.binding.note;
  const fallback = [ {id:"read",title:"Read document",state:ready ? "passed" : "not-run"},
    ...["Netlist connectivity", "Electrical rules (ERC)", "Board rules (DRC)", "Copper clearance", "Placement rules", "Zone fill", "Conversion", "Fabrication export"].map(title => ({title, state:"not-run"})) ];
  for (const card of data?.cards || fallback) {
    const details = document.createElement("details"), state = REVIEW_STATE[card.state] ? card.state : "limited";
    details.dataset.card = card.id || card.title;
    details.innerHTML = `<summary><span>${esc(card.title)}</span><span class="reviewState ${state}">${REVIEW_STATE[state]}</span></summary>`;
    const add = text => { const p = document.createElement("p"); p.textContent = text; details.appendChild(p); };
    if (card.evidence) add(`Evidence: ${card.evidence}`);
    for (const reason of card.reasons || []) add(reason);
    if (card.binding) add(card.binding.note);
    if ((card.missing || []).length) add(`Not run: ${card.missing.join(", ")}`);
    if (state === "not-run") add(RUNS.enabled && CARD_STAGES[card.id] ? "Not run yet: Run checks it now, on this server." : "No result supplied. Run fenolite check separately and reopen with --check FILE, or attach recorded conversion/export results with --report FILE.");
    for (const stage of card.stages || []) {
      add(`${stage.name}: ${stage.status || "unknown"} · ${stage.evidence}`);
      for (const reason of stage.reasons || []) add(reason);
      if (stage.limits && Object.keys(stage.limits).length) add(`Report limits: ${JSON.stringify(stage.limits)}`);
    }
    runCardControl(details, card); box.appendChild(details);
  }
  buildRunPanel();
  buildActionPanel();
  REVIEW.items = ready ? [ ...(S.check?.findings || []).map((item, i) => ({...item, checkIndex:i})), ...(S.run_findings || []).map((item, i) => ({...item, runIndex:i})), ...(data?.operation_findings || []) ] : [];
  const stage = $("reviewStage"), chosen = stage.value;
  stage.innerHTML = '<option value="">All stages</option>';
  for (const name of [...new Set(REVIEW.items.map(x => x.stage || "unassigned"))].sort()) {
    const option = document.createElement("option"); option.value = name; option.textContent = name; stage.appendChild(option);
  }
  stage.value = [...stage.options].some(o => o.value === chosen) ? chosen : "";
  REVIEW.selected = -1; filterReviewFindings();
}
export function filterReviewFindings() {
  const severity = $("reviewSeverity").value, stage = $("reviewStage").value, q = $("reviewSearch").value.trim().toLowerCase();
  REVIEW.matches = REVIEW.items.map((x, i) => i).filter(i => {
    const x = REVIEW.items[i]; return (!severity || x.severity === severity) && (!stage || (x.stage || "unassigned") === stage) &&
      (!q || [x.code, x.message, x.where, x.hint].some(v => String(v || "").toLowerCase().includes(q)));
  });
  if (!REVIEW.matches.includes(REVIEW.selected)) REVIEW.selected = REVIEW.matches[0] ?? -1;
  const box = $("reviewFindings"); box.innerHTML = "";
  $("reviewCount").textContent = REVIEW.items.length ? `${REVIEW.matches.length} of ${REVIEW.items.length} reported findings` : "No findings supplied. This does not mean the project passed its checks.";
  if (REVIEW.items.length && !REVIEW.matches.length) $("reviewCount").textContent += " — no matches";
  for (const i of REVIEW.matches) {
    const x = REVIEW.items[i], button = document.createElement("button"); button.type = "button";
    button.textContent = `${x.severity}: ${x.code} — ${x.message}`; button.setAttribute("aria-pressed", String(i === REVIEW.selected));
    button.onclick = () => { REVIEW.selected = i; filterReviewFindings(); }; box.appendChild(button);
  }
  $("reviewPrevious").disabled = $("reviewNext").disabled = !REVIEW.matches.length;
  const detail = $("reviewDetail"), x = REVIEW.items[REVIEW.selected]; detail.innerHTML = "";
  if (!x) return;
  const h = document.createElement("h3"); h.textContent = `${x.code} · ${x.severity}`; detail.appendChild(h);
  for (const text of [x.message, `Stage: ${x.stage || "unassigned"} · evidence: ${x.evidence || "UNKNOWN"}`, x.where && `Where: ${x.where}`, x.hint && `Guidance: ${x.hint}`,
    x.at ? "Locate highlights the recorded geometry; review does not mark the problem fixed." : "No position on this document. Use the location and original guidance above."]) {
    if (!text) continue; const p = document.createElement("p"); p.textContent = text; detail.appendChild(p);
  }
  if (x.checkIndex != null && x.at) {
    const button = document.createElement("button"); button.textContent = "Locate in drawing";
    button.onclick = () => { st.checks = true; setProjectReview(false); selectFinding(x.checkIndex); }; detail.appendChild(button);
  }
  runLocateButton(x, detail);
  actWaiveButton(x, detail);
}
for (const id of ["reviewSeverity", "reviewStage"]) $(id).onchange = filterReviewFindings;
$("reviewSearch").oninput = filterReviewFindings;
export function stepReviewFinding(direction) {
  if (!REVIEW.matches.length) return;
  const k = REVIEW.matches.indexOf(REVIEW.selected);
  REVIEW.selected = REVIEW.matches[(k + direction + REVIEW.matches.length) % REVIEW.matches.length]; filterReviewFindings();
}
$("reviewPrevious").onclick = () => stepReviewFinding(-1);
$("reviewNext").onclick = () => stepReviewFinding(1);
// ---- Run controls (c0245): a Run button on each card whose stages this server can run, the panel "Run from
// this page", and Locate for the findings of a ready or equivalent run. The client is review/runs.
export function runCardControl(details, card) {   // a Run control on a card whose stages this server can run
  if (!RUNS.enabled || !DOC) return;
  const offered = runStages(), stages = (CARD_STAGES[card.id] || []).filter(s => offered.includes(s));
  if (!stages.length) return;
  const b = document.createElement("button"); b.className = "runCard"; b.textContent = "Run"; b.dataset.runCard = card.id;
  b.title = `Run ${stages.join(", ")} now (fenolite check; nothing is written)`; b.disabled = !!RUNS.job;
  b.setAttribute("aria-label", `Run ${card.title}`);
  b.onclick = e => { e.preventDefault(); e.stopPropagation(); startRun("check", { stages }); };
  details.querySelector("summary").insertBefore(b, details.querySelector(".reviewState"));
}
function runBox(title, body) { const s = document.createElement("div"); s.className = "runBox"; s.innerHTML = `<h4>${esc(title)}</h4>`; body(s); return s; }
function runChecks(name, values, chosen) {   // a grid of checkboxes, one per value
  const g = document.createElement("div"); g.className = "runGrid";
  for (const v of values) { const l = document.createElement("label"); l.innerHTML = `<input type="checkbox" name="${esc(name)}" value="${esc(v)}" ${chosen.includes(v) ? "checked" : ""}> ${esc(v)}`; g.appendChild(l); }
  return g;
}
function picked(box, name) { return [...box.querySelectorAll(`input[name="${name}"]:checked`)].map((i: HTMLInputElement) => i.value); }
export function buildRunPanel() {
  const panel = $("runPanel"); if (!panel) return; panel.innerHTML = "";
  panel.hidden = !RUNS.enabled || !DOC || !(DOC.viewable || DOC.kind === "project");
  if (panel.hidden) return;
  const busy = !!RUNS.job, cmds = RUNS.offer.commands || {};
  const head = document.createElement("h3"); head.textContent = "Run from this page"; panel.appendChild(head);
  const note = document.createElement("p"); note.className = "notes";
  note.textContent = "Read-only commands run on this server in the project folder; nothing is written. Results replace the stages they ran and stay bound to the file's revision.";
  panel.appendChild(note);
  const stages = runStages(), defaults = runAltium() ? stages : (cmds.check?.options?.stages?.default || []);
  panel.appendChild(runBox("Checks", s => {
    s.appendChild(runChecks("stage", stages, defaults));
    const row = document.createElement("div"); row.className = "runRow";
    row.innerHTML = '<button id="runChecks">Run checks</button><button id="runAll">Run all checks</button>'; s.appendChild(row);
    row.querySelector<HTMLButtonElement>("#runChecks").onclick = () => { const chosen = picked(s, "stage"); if (chosen.length) startRun("check", { stages: chosen }); else runSay("failed", "Choose at least one stage."); };
    row.querySelector<HTMLButtonElement>("#runAll").onclick = () => startRun("check", {});
  }));
  if (cmds.analyze && DOC.kind === "pcb") panel.appendChild(runBox("Analyze", s => {
    const o = cmds.analyze.options.kinds; s.appendChild(runChecks("kind", o.choices, o.default));
    const b = document.createElement("button"); b.id = "runAnalyze"; b.textContent = "Analyze"; s.appendChild(b);
    b.onclick = () => { const chosen = picked(s, "kind"); startRun("analyze", chosen.length ? { kinds: chosen } : {}); };
  }));
  if (cmds.ready && !runAltium()) panel.appendChild(runBox("Readiness", s => {
    s.innerHTML += '<label class="runOpt"><input type="checkbox" id="runNoKicad"> without kicad-cli (ERC and DRC skipped)</label>';
    const b = document.createElement("button"); b.id = "runReady"; b.textContent = "Check readiness"; s.appendChild(b);
    b.onclick = () => startRun("ready", s.querySelector("#runNoKicad").checked ? { no_kicad: true } : {});
  }));
  const others = (PROJECT ? PROJECT.groups.flatMap(g => g.documents) : []).filter(d => d.present && d.viewable && d.id !== DOC.id && d.kind === DOC.kind);
  if (cmds.equivalent && others.length) panel.appendChild(runBox("Compare with", s => {
    const sel = document.createElement("select"); sel.id = "runOther"; sel.setAttribute("aria-label", "Document to compare with");
    for (const d of others) { const o = document.createElement("option"); o.value = d.id; o.textContent = d.name; sel.appendChild(o); }
    const b = document.createElement("button"); b.id = "runEquivalent"; b.textContent = "Compare"; s.append(sel, b);
    b.onclick = () => startRun("equivalent", { b: sel.value });
  }));
  for (const b of panel.querySelectorAll("button")) b.disabled = busy;
}
export function runLocateButton(x, detail) {   // Locate for a finding of a ready or equivalent run
  if (x.runIndex == null || !x.at) return;
  const button = document.createElement("button"); button.textContent = "Locate in drawing";
  button.onclick = () => { setProjectReview(false); const b = x.box || [x.at[0], x.at[1], x.at[0], x.at[1]], m = Math.max(b[2] - b[0], b[3] - b[1], 6) * 0.8;
    fit([b[0] - m, b[1] - m, b[2] + m, b[3] + m]); showInfo(`<b>${esc(x.code)}</b> · ${esc(x.severity)}<br>${esc(x.message)}<br>From ${esc(x.stage)} · evidence ${esc(x.evidence || "?")}`); };
  detail.appendChild(button);
}
