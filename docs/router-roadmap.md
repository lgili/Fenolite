# Router roadmap and remaining specifications

Planning audit: 2026-11-03. This page separates proposed work from locally implemented, not yet merged behavior.

## Source of the phases

The original tracked study is the [c0222 design](../openspec/changes/archive/2026-10-29-c0222-net-roles/design.md),
sections “Plan of phases 1 to 4” and its revised plan. It defines **five phases numbered 0 through 4**,
with development order **0 → 1 → 2 → 4 → 3**. No numbered phase 5 appears in that study.
Phase 3 comprises search, electrical-role costs and negotiated congestion; it is not just more fixed patterns.

The [c0280 design](../openspec/changes/archive/2026-11-04-c0280-route-proposals/design.md), optional external candidate
family and open questions 6–7, additionally defers external-router proposals and the viewer drawing.
Its existing server data/actions do not establish that the frontend draws proposals.
The acceptance work below consolidates the original review, tidy, checking and output obligations;
it does not introduce a historical “phase 5”.

## Baseline inspected

These proposals start from `origin/router-c0280` at
`13419373315b7ba197862f9340c98f2a5dbbb293`. Its
[CI run 41294183261](https://github.com/lgili/Fenolite/actions/runs/41294183261)
completed successfully (13 jobs). That run proves the baseline, not the proposals below.
The new working branch is `codex/router-next-specs`; no integration or release is implied.

| Phase | Existing change | Status on the inspected baseline |
| --- | --- | --- |
| Pattern foundation | c0228-octilinear-router | Archived; bounded fixed shapes, not general maze search |
| 0: electrical intent | c0222-net-roles | Archived; roles, inference, confirmation and checks |
| 1: power copper | c0243-role-copper | Archived; generated copper and preservation manifest |
| 2: critical routes | c0244-critical-routes | Archived; constrained gate/Kelvin routes and corridors |
| 4: propose and lock | c0280-route-proposals | 25/25 tasks checked on this baseline; external candidates and frontend drawing explicitly deferred |
| 3: search and negotiation | New changes below | Missing on the baseline; c0365 search implemented locally on the follow-up branch, unmerged |

The separate CAC integration adds its own c0280 integration/CI task; this page does not close it.
Direct native Altium editing remains c0241-altium-edit-sessions, not a missing router phase.

## Proposed changes

c0365 tasks 1–6 are locally implemented with focused proofs; exact-head CI and closing tasks remain open.
c0366–c0370 remain proposals with implementation tasks unchecked. Dependencies mean
required interfaces/evidence, not permission to merge unrelated working branches.

| Change | Scope | Dependencies |
| --- | --- | --- |
| [c0365-router-search](../openspec/changes/c0365-router-search/proposal.md) | Phase 3A: opt-in bounded A*, multilayer search and through vias | c0228, c0280 |
| [c0366-router-role-costs](../openspec/changes/c0366-router-role-costs/proposal.md) | Phase 3B: electrical hard constraints, role costs, honest ground-reference facts | c0365, c0222, c0243, c0244 |
| [c0367-router-negotiated-reroute](../openspec/changes/c0367-router-negotiated-reroute/proposal.md) | Phase 3C: congestion negotiation and atomic joint alternatives | c0365, c0366, c0280 |
| [c0368-router-external-candidates](../openspec/changes/c0368-router-external-candidates/proposal.md) | Deferred phase 4: explicit local subprocess candidates via `--propose-with` | c0280 and existing plugin/budget contracts |
| [c0369-router-proposal-viewer](../openspec/changes/c0369-router-proposal-viewer/proposal.md) | Deferred phase 4: candidate geometry, facts and reviewed viewer actions | c0280, c0303, c0305; c0367 for bundle controls |
| [c0370-router-completion-review](../openspec/changes/c0370-router-completion-review/proposal.md) | Cross-cutting workflow, tidy, output and scale acceptance | c0365–c0369 for final acceptance; existing stages for early documentation |

Implement c0365 → c0366 → c0367 in order. c0368 and the independent-candidate part of c0369 can
advance separately after their dependencies are available. Finish bundle controls after c0367.
Start c0370's existing-workflow documentation early; its integrated family/scale proofs wait for
all required implementations. Each change carries its own local proofs and exact-head full CI gate.
No implementation task is closed by writing this page.

## Per-board execution order

Development phase numbers are not the recommended order of operations on one board:

1. Inspect capabilities, establish the placed board and confirm inferred roles and user limits.
2. Route critical groups and preserve their locked copper and corridors.
3. Generate power/ground copper around those protected items.
4. Propose remaining connections, inspect geometry/facts, and explicitly accept or reject alternatives.
5. Optionally review a scoped tidy plan; preserve manual and locked copper.
6. Fill, check connectivity/roles/DRC, inspect remaining opens and export/render the checked result.

This aligns with the existing `board-power` agent guide. c0370 reconciles the older phase-number
ordering in `docs/roles.md`. Every writing stage uses its own reviewed transaction; the sequence
is not falsely advertised as one atomic write. A proposal, rejection, timeout or unknown check
never counts as a physical connection or manufacturing approval.

## Boundaries and later decisions

- Ordinary connections stay proposed, never silently accepted. Search and negotiation are opt-in.
- No runtime dependency enters the core; external copyleft tools stay across subprocess boundaries.
- No private boards, employer calculations or derived fixtures enter this repository.
- User electrical limits remain authoritative; no invented creepage or fabrication defaults.
- Blind/microvias, impedance solvers, length tuning, native acceleration and automatic candidate
  selection are outside these changes. Pair/group maze search needs a separate joint-search proof;
  existing pattern/group support remains and unsupported search is explicit.
- Altium output uses checked KiCad copper followed by conversion/readback (`INFERRED`). Native
  validation and direct `.PcbDoc` editing are separate gates, not claimed complete here.
- Scope is the original two/four-layer, roughly 150-part target, with measured resource evidence;
  neither route completion nor a runtime deadline is guaranteed for arbitrary boards.
