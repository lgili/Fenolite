// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// ================================================================== project review: recorded evidence and a guided finding list (c0239)
import { $, esc } from "../core/dom";
import { setSidebar } from "../core/input";
import { DOC, S, st } from "../core/state";
import { selectFinding } from "../review/check";
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
    if (state === "not-run") add("No result supplied. Run fenolite check separately and reopen with --check FILE, or attach recorded conversion/export results with --report FILE.");
    for (const stage of card.stages || []) {
      add(`${stage.name}: ${stage.status || "unknown"} · ${stage.evidence}`);
      for (const reason of stage.reasons || []) add(reason);
      if (stage.limits) add(`Report limits: ${JSON.stringify(stage.limits)}`);
    }
    box.appendChild(details);
  }
  REVIEW.items = ready ? [ ...(S.check?.findings || []).map((item, i) => ({...item, checkIndex:i})), ...(data?.operation_findings || []) ] : [];
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
