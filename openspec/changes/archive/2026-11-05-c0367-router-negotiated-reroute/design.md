## Context

Independent paths can consume the only corridor available to another net. The original phase 3 includes bounded negotiation across nets, beyond repeating fixed patterns.

Original plan: archived c0222-net-roles design, sections "Plan of phases 1 to 4" and
its revised plan; c0280-route-proposals design records the deferred external candidates and
viewer drawing. See `docs/router-roadmap.md` for the inspected branch and dependencies.

## Dependencies and scope

c0365-router-search, c0366-router-role-costs and c0280-route-proposals. Negotiate provisional routes for selected subjects in private memory and present jointly valid alternatives as atomic bundles. Protect manual copper, existing decisions and electrical corridors.

## Modules and public interface

Create routing/negotiate.py and routing/bundles.py; extend routing/protocol.py, routing/decisions.py, routing/propose.py and cli/_propose.py. negotiate(job, subjects, limits) is internal. Add additive bundle membership/fingerprints to the decision and proposal contracts; older independent candidates remain readable.

Extend --router-option with negotiate=off|on and negotiate-max-rounds=N, valid only in octilinear proposal/accept/reject modes with bounded search (repeat options to regenerate reviewed bundle IDs, as c0365 does). Default off. Existing --accept/--reject/--replay/--forget accept a bundle ID atomically; accepting a coupled member alone is a usage refusal naming the bundle.

## Decisions

Start from c0365 search, maintain temporary occupancy and nonnegative historical congestion costs, and retry only routes owned by this negotiation job. Stable subject ordering and integer costs bound rounds/states under the one job budget. Existing copper, accepted decisions, role-copper manifests and critical-route corridors are immutable obstacles. Treat any supported pair/group as one routing unit; otherwise refuse it. Temporary overlaps are private exploration state, never exportable copper. Validate the final combined geometry, role findings and connectivity before emitting a bundle. Bundle identity hashes all member geometries, subjects and input fingerprints. Accept/reject/replay/forget are all-or-nothing decisions, with lock and rollback semantics inherited from reviewed plans. Preserve legacy decision-file reading; fail explicitly on an unsupported future schema rather than discarding decisions.

All model geometry uses integer nanometres and microdegrees. The core remains stdlib-only.
Use only authored fixtures or declared public inputs; never port external router implementation
code. Record primary-source facts in the evidence registry before using them. No format fact is
introduced by this proposal. Any future format extension needs its own sourced format evidence.

## Contracts, failure and compatibility

The existing reviewed-plan/confirm protocol remains authoritative. Candidate generation changes
no project files. Changed board, role, profile or decision inputs invalidate the reviewed plan.
Keep existing exit codes, receipt hashes and rollback/recovery semantics. Do not allocate a new
FEN code until existing codes and concurrent changes have been inspected; register and document
any necessary new finding with a tested guide line. Preserve existing defaults and decision files.

A fixed seed, timestamp and deterministic resource bound must yield stable bytes. Wall-clock
exhaustion may stop at a different expansion; report that limitation, isolate timing telemetry
and never call a truncated result exhaustive. All nested work consumes the same job budget.

## Evidence and validation before merge

Authored unit and focused contract tests establish `INFERRED` behavior. CI's applicable pinned
KiCad versions must judge generated copper and connectivity before `KICAD-VERIFIED` is claimed.
A tool missing locally is not a passing oracle. Retain before/after findings, versions, limits
and hashes. Altium conversion/readback remains `INFERRED`; native validation is separate.
Visual references, when applicable, come from the pinned CI Chromium and require image review.
Only quick/focused checks run locally; complete checks run in CI on the exact proposed head.
If closing evidence or changelog edits change that head, the final edited head requires its own
CI validation before merge/archive; an earlier green run is not transferable.

## Delivery and risks

Follow tasks in order; each numbered task is at most one design-day. If a task grows, split it
before implementation. Mark it complete only after its stated proof passes, adding a dated note.
Rebase/reconcile shared interfaces with concurrent work before implementation. Shared registry,
protocol and guide edits must remain minimal. Public options, result fields and findings need
guide coverage; each guide page stays at most 12000 bytes.

Risk areas are combinatorial resource growth, stale geometry, partial writes, unsupported
constraints and inflated evidence claims. Test negative cases as well as successful examples.
Default opt-in behavior and explicit unresolved results bound the rollout.

## Concrete bounded kernel — 2026-11-03

The original routing world is immutable. Only a private subject-to-candidate map is replaced.
Each sorted subject searches against fixed copper and hard role fields; other provisional copper
contributes a nonnegative swept-geometry penalty. Conflicting segments add nonnegative history
for subsequent rounds. The coefficients are authored software preferences, not physical rules.
One discovered-state budget is deducted across every A* call and round, in addition to the
explicit round/via bounds and shared deadline/cancellation. Geometry includes full through barrels.
A legal set is still withheld until whole-bundle connectivity and the existing final judges pass.
All independent alternatives are replaced by the single bundle in negotiated mode, preventing
an alternate path around the atomic-member rule. Default-off behavior remains unchanged.

## Selection and replay compatibility — 2026-11-03

Negotiated accept/reject allows the same net/kind/group selectors as proposal generation; these
must be repeated for a selected subset. `result.next` includes those selectors and router controls.
The candidate-count knob does not change the single joint alternative and is excluded from its
identity. The decision record is a reviewed-plan dependency, not a geometry-generation input;
rejecting an unchanged alternative therefore does not rename it on the next proposal.
`--replay [BUNDLE]` keeps bare replay of all decisions. Dispatch normalizes a legacy bare replay
before PATH; members cannot be independently replayed. Replay rechecks current hard fields and
accepts `--requirements FILE` without search options, so absent HV distances fail closed.
