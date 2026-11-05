// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// Each decision previews through the existing action protocol; confirmation belongs to its dialog.
import * as preact from "preact";
import { ACTS, actPlan } from "../actions/actions";
import { draw } from "../board/draw";
import { $ } from "../core/dom";
import { DOC, S } from "../core/state";
import { fit } from "../core/viewport";
import { proposalFacts, proposalScene, proposalBundleModels, PROPOSAL_WRITABLE_FAMILIES, PROPOSALS, ProposalCandidate, ProposalSubject } from "../proposals";
import { showSection } from "../ui/section";
import { selectNetAt } from "./review";
function focusProposal(subject: ProposalSubject, candidate?: ProposalCandidate) {
  PROPOSALS.focused = candidate?.id || "";
  const net = S.nets.indexOf(subject.net); if (net >= 0) selectNetAt(net);
  if (subject.box) fit(subject.box); buildProposals(); draw();
}
export function proposalWriteReason(candidate?: ProposalCandidate) {
  const data = proposalScene(S);
  if (!LIVE || !ACTS.enabled || !DOC || ACTS.doc !== DOC.id) return "Read-only page or actions unavailable.";
  if (data?.stale) return "Proposals predate a project write; run proposals again.";
  if (!data?.sha256 || !S.meta?.sha256 || data.sha256 !== S.meta.sha256) return "Proposals are stale or unbound; run proposals again.";
  if (data.controls && data.controls.portable !== true) return "This router/tool configuration cannot be replayed from the viewer.";
  if (data.controls && data.controls.schema !== "fenolite.proposal_controls.v0") return "Unsupported regeneration controls.";
  if (candidate && (!candidate.id || !/^c-[0-9a-f]{16}$/.test(candidate.id))) return "No writable candidate ID.";
  if (candidate && !PROPOSAL_WRITABLE_FAMILIES.has(candidate.source || "")) return "Unknown family: inspection only.";
  if (candidate?.bundle) return "Review the complete atomic bundle.";
  if (candidate && !data.controls && (candidate.source === "search" || candidate.source?.startsWith("external:"))) return "Regeneration controls are missing; rerun proposals.";
  return "";
}
async function reviewProposalDecision(action: "route-accept" | "route-reject", id: string, reason: string, button: HTMLButtonElement) {
  button.disabled = true;
  try { await actPlan(action, {candidates:[id], ...(action === "route-reject" && reason ? {reason} : {})}); }
  finally { buildProposals(); }
}
function ProposalUnitDecision({ id, why, rejected = false }: {id: string; why: string; rejected?: boolean}) {
  if (!LIVE || !ACTS.enabled) return null;
  const reason = {current:null as HTMLInputElement | null};
  const busy = !!ACTS.job, accept = ACTS.offer?.["route-accept"], reject = ACTS.offer?.["route-reject"];
  return <div class="proposalDecision">
    {why ? <p class="hint">{why}</p> : null}
    <button type="button" class="tb small" data-proposal-action="route-accept" disabled={!!why || busy || !accept?.available || rejected}
      onClick={e => reviewProposalDecision("route-accept", id, "", e.currentTarget as HTMLButtonElement)}>Review accept plan…</button>
    <label class="actField">Rejection reason (optional)<input ref={reason} maxlength={300} aria-label={`Rejection reason ${id}`} /></label>
    <button type="button" class="tb small" data-proposal-action="route-reject" disabled={!!why || busy || !reject?.available}
      onClick={e => reviewProposalDecision("route-reject", id, reason.current?.value.trim() || "", e.currentTarget as HTMLButtonElement)}>Review reject plan…</button>
  </div>;
}
function ProposalDecisionButtons({ candidate }: {candidate: ProposalCandidate}) {
  if (candidate.bundle) return <p class="hint">Use the complete atomic bundle controls; members cannot be decided alone.</p>;
  return <ProposalUnitDecision id={candidate.id} why={proposalWriteReason(candidate)} rejected={candidate.rejected} />;
}
function ProposalBundleCards({ data }: {data: any}) {
  return <>{proposalBundleModels(data).map(unit => <section class="proposalBundle" key={unit.bundle.id} data-bundle={unit.bundle.id}>
    <h3>Atomic alternative</h3><strong>{unit.bundle.id}</strong>
    <p>{`All ${unit.bundle.members?.length || 0} members are accepted or rejected together, including hidden overlays.`}</p>
    <p>{unit.reason}</p><ul>{unit.members.map(row => <li key={row.candidate.id}>{`${row.subject.net || "unknown net"}: ${row.candidate.id}`}</li>)}</ul>
    <button type="button" class="tb small" disabled={!unit.members.length} onClick={() => {
      PROPOSALS.focused = unit.bundle.id;
      const boxes = unit.members.map(row => row.subject.box).filter(Boolean);
      if (boxes.length) fit([Math.min(...boxes.map(b=>b[0])),Math.min(...boxes.map(b=>b[1])),Math.max(...boxes.map(b=>b[2])),Math.max(...boxes.map(b=>b[3]))]);
      buildProposals(); draw();
    }}>Inspect whole bundle</button>
    <ProposalUnitDecision id={unit.bundle.id} why={proposalWriteReason() || unit.reason} />
    <details><summary>Bound input fingerprint</summary><p>{unit.bundle.fingerprint || "unknown"}</p></details>
  </section>)}</>;
}
function ProposalCandidateCard({ candidate, subject }: { candidate: ProposalCandidate; subject: ProposalSubject }) {
  const id = candidate.id || "unknown", locked = candidate.locked || PROPOSALS.data?.locked?.some(row => row.candidate === id && row.present);
  return <article class="proposalCandidate" data-candidate={id}>
    <div class="proposalControls">
      <label><input type="checkbox" checked={!PROPOSALS.hidden.has(id)} aria-label={`Show candidate ${id}`}
        onChange={e => { const on = (e.currentTarget as HTMLInputElement).checked; on ? PROPOSALS.hidden.delete(id) : PROPOSALS.hidden.add(id); draw(); }} /> Show</label>
      <button type="button" class="tb small" onClick={() => focusProposal(subject, candidate)} aria-label={`Focus candidate ${id}`}>Focus / cross-probe</button>
    </div>
    <strong>{id}</strong><div>{candidate.source || "unknown family"}</div>
    <p class="hint">{locked ? "Locked decision" : "Provisional · dashed copper"}{candidate.rejected ? " · rejected" : ""}</p>
    {candidate.bundle ? <p>{`Atomic bundle: ${candidate.bundle}`}</p> : null}
    {(candidate.relaxed || []).length ? <p>{`Relaxations: ${candidate.relaxed.join(", ")}`}</p> : null}
    {candidate.unknown_geometry ? <p class="notes">Some geometry is unknown and is not drawn.</p> : null}
    <dl>{proposalFacts(candidate).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    <ProposalDecisionButtons candidate={candidate} />
    <details><summary>Geometry and tool details</summary><pre>{JSON.stringify({ layers: (candidate.polylines || []).map(p => p.layer), vias: candidate.vias, tool: candidate.tool ?? "unknown" }, null, 2)}</pre></details>
  </article>;
}
export function buildProposals() {
  const box = $("proposalList"); if (!box) return;
  const data = proposalScene(S); showSection("proposals", !!data, data?.proposals?.length || 0, "Route proposals");
  if (data !== PROPOSALS.data) { PROPOSALS.data = data; PROPOSALS.hidden.clear(); PROPOSALS.focused = ""; }
  if (!data) { preact.render(null, box); return; }
  preact.render(<>
    <p class="hint">Inspect alternatives in generation order. Dashed cyan copper is provisional; squares mark endpoints. Nothing is selected for acceptance.</p>
    <p>{`Evidence: ${data.evidence?.level || "unknown"}`}</p>
    {data.stale ? <p class="notes">Proposals predate a project write. Run proposals again before deciding.</p> : null}
    {(data.notes || []).map((note, index) => <p class="notes" key={index}>{note}</p>)}
    <ProposalBundleCards data={data} />
    {(data.proposals || []).map(subject => <section class="proposalSubject" key={subject.id} data-proposal={subject.id}>
      <h3>{subject.net || "unknown net"}</h3><p>{subject.subject || subject.id || "unknown subject"}</p>
      <button type="button" class="tb small" onClick={() => focusProposal(subject)}>Focus endpoints</button>
      <p>{(subject.ends || []).map(end => `${end.name || end.kind || "unknown"} [${end.layers.join(", ")}]`).join(" → ")}</p>
      {subject.reason ? <p class="notes">{`Unresolved: ${subject.reason}`}</p> : null}
      {!subject.candidates?.length ? <p class="hint">No candidate. This subject remains unresolved.</p> : null}
      {(subject.candidates || []).map(candidate => <ProposalCandidateCard key={candidate.id} candidate={candidate} subject={subject} />)}
    </section>)}
    {(data.locked || []).length ? <details><summary>Locked decisions</summary><ul>{data.locked.map(row => <li key={row.candidate}>{`${row.candidate} · ${row.present ? "present" : "missing copper"}`}</li>)}</ul></details> : null}
    <p class="hint">{LIVE ? "Each decision previews a plan; only its explicit confirmation writes files." : "Read-only exported page: no project-writing controls."}</p>
  </>, box);
}
