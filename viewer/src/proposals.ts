// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// c0369: the additive view_proposals.v0 contract. Unknown families are text and generic geometry.
export interface ProposalLine { layer: string; width: number; points: number[][]; }
export interface ProposalVia { at: number[]; diameter: number; drill?: number; layers: string[]; }
export interface ProposalEnd { kind?: string; name?: string; at?: number[]; layers: string[]; }
export interface ProposalCandidate {
  id?: string; source?: string; relaxed?: string[]; polylines: ProposalLine[]; vias: ProposalVia[];
  facts?: Record<string, unknown>; rejected?: boolean; locked?: boolean; bundle?: string;
  tool?: Record<string, unknown>; unknown_geometry?: boolean;
}
export interface ProposalSubject {
  id?: string; subject?: string; kind?: string; net?: string; box?: number[];
  ends?: ProposalEnd[]; candidates: ProposalCandidate[]; reason?: string;
}
export interface ProposalScene {
  schema: string; proposals: ProposalSubject[]; mm?: boolean; sha256?: string; stale?: boolean; notes?: string[];
  controls?: {schema?: string; portable?: boolean; router_options?: string[]};
  bundles?: { id: string; members: string[]; subjects?: string[]; fingerprint?: string }[];
  locked?: { candidate: string; subject: string; present: boolean }[];
  evidence?: { level?: string }; counts?: { proposals: number; candidates: number };
}
export const PROPOSALS = { data: null as ProposalScene | null, hidden: new Set<string>(), focused: "" };
export function proposalScene(scene): ProposalScene | null {
  return scene && !scene.kind && scene.proposals?.schema === "fenolite.view_proposals.v0" ? scene.proposals : null;
}
export function proposalsToMM(scene) {
  const data = proposalScene(scene); if (!data || data.mm) return; data.mm = true;
  const point = p => p.map(v => v * 0.001);
  for (const subject of data.proposals || []) {
    if (subject.box) subject.box = point(subject.box);
    for (const end of subject.ends || []) if (end.at) end.at = point(end.at);
    for (const candidate of subject.candidates || []) {
      for (const line of candidate.polylines || []) { line.width *= 0.001; line.points = line.points.map(point); }
      for (const via of candidate.vias || []) {
        via.at = point(via.at); via.diameter *= 0.001; if (via.drill != null) via.drill *= 0.001;
      }
    }
  }
}
export function proposalFacts(candidate: ProposalCandidate): [string, string][] {
  const f = candidate.facts || {}, text = v => v == null ? "unknown" : typeof v === "object" ? JSON.stringify(v) : String(v);
  return [["Length (nm)", text(f.length)], ["Vias", text(f.vias)], ["Layers", text(f.layers)],
    ["Open connections", text(f.open)], ["Copper findings", text(f.copper)],
    ["Role findings", text(f.roles)], ["Not measured", text(f.not_evaluated)],
    ["Role/reference bounds", text(f.role_fields)]];
}

export const PROPOSAL_WRITABLE_FAMILIES = new Set(["shape", "z-shape", "via-l", "fanout", "role", "search", "external:kicadroutingtools", "external:freerouting"]);
export function proposalBundleModels(data: ProposalScene) {
  const rows = (data.proposals || []).flatMap(subject => (subject.candidates || []).map(candidate => ({subject, candidate})));
  const bundles = Array.isArray(data.bundles) ? data.bundles.filter(b => b && typeof b === "object") : [];
  const counts = new Map<string, number>(), claims = new Map<string, number>(), ids = new Map<string, number>();
  for (const {candidate} of rows) counts.set(candidate.id, (counts.get(candidate.id) || 0) + 1);
  for (const bundle of bundles) {
    ids.set(bundle.id, (ids.get(bundle.id) || 0) + 1);
    if (Array.isArray(bundle.members)) for (const member of bundle.members) claims.set(member, (claims.get(member) || 0) + 1);
  }
  return bundles.map(bundle => {
    const names = Array.isArray(bundle.members) ? bundle.members : [];
    const members = names.map(id => rows.find(row => row.candidate.id === id)).filter(Boolean);
    const declared = rows.filter(row => row.candidate.bundle === bundle.id);
    const subjects = members.map(row => row.subject.subject);
    const valid = /^b-[0-9a-f]{16}$/.test(bundle.id) && ids.get(bundle.id) === 1 &&
      /^[0-9a-f]{64}$/.test(bundle.fingerprint || "") && names.length >= 2 &&
      new Set(names).size === names.length && members.length === names.length &&
      names.every(id => /^c-[0-9a-f]{16}$/.test(id) && counts.get(id) === 1 && claims.get(id) === 1) &&
      members.every(row => row.candidate.bundle === bundle.id && PROPOSAL_WRITABLE_FAMILIES.has(row.candidate.source)) &&
      declared.length === names.length && new Set(subjects).size === subjects.length &&
      JSON.stringify(subjects) === JSON.stringify(bundle.subjects) &&
      data.controls?.schema === "fenolite.proposal_controls.v0" &&
      Array.isArray(data.controls.router_options) && data.controls.router_options.includes("negotiate=on");
    const display = {...bundle,
      id: typeof bundle.id === "string" ? bundle.id : "unknown bundle",
      fingerprint: typeof bundle.fingerprint === "string" ? bundle.fingerprint : "unknown"};
    return {bundle: display, members, valid, reason: valid ? "" : "Incomplete or ambiguous bundle metadata: inspection only."};
  });
}
