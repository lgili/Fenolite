## Context

c0280 explicitly deferred --propose-with. Existing external routers can route a job, but they do not yet supply reviewable, isolated candidates in the proposal workflow.

Original plan: archived c0222-net-roles design, sections "Plan of phases 1 to 4" and
its revised plan; c0280-route-proposals design records the deferred external candidates and
viewer drawing. See `docs/router-roadmap.md` for the inspected branch and dependencies.

## Dependencies and scope

c0280-route-proposals and the existing routing plugin/budget contracts (c0016, c0023, c0109). Adapt locally available external routers into candidate generators using existing subprocess adapters, shared budgets, strict board-delta validation and the same measured facts as internal candidates.

## Modules and public interface

Create routing/external_candidates.py and extend routing/propose.py, routing/select.py and cli/_propose.py. Reuse existing adapters and routing/budget.py; do not create a second external process stack. An internal generate_external(job, subjects, routers) returns validated candidates or explicit refusals.

Add repeatable --propose-with ROUTER, valid with --propose and with --accept/--reject when regenerating those proposals; --confirm consumes staged bytes and never reruns a router. Expose supported local routers/candidate availability in capabilities. Candidate sources use external:<router> plus tool version and reproducibility metadata. Missing requested tools keep the existing missing-tool exit contract.

## Decisions

Restrict each adapter to the selected subject scope; compare its output against the immutable baseline rather than trusting preserved external IDs. Reject moved pads/footprints, changed outline/stackup/rules, removed/edited existing copper or unselected-net additions. Canonicalize only verified new copper into stable IDs. Validate through vias across their full barrel and enforce pair/group atomicity or refuse unsupported subjects. A whole-job adapter is usable only if its delta passes the same scope proof. Every process shares one Budget and cancellation path; kill and reap process trees and disregard killed/partial output. No implicit fetch or network fallback. Order family dispatch stably; clock-truncated results honestly report the subset attempted. A verified candidate still requires explicit reviewed acceptance.

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

## Implementation refinements (2026-11-03)

The first supported scope is one ordinary connection. Unsupported groups, named/model pairs,
role routes, escape/fanout and arcs are refused before dispatch. The CLI owns connectivity and
role/copper judges; routing receives callbacks and never imports analysis or backend plugins.
Local KiCadRoutingTools and a local Freerouting jar are the adapter allowlist. Container
references are not supported in candidate mode: they could pull an image implicitly. Existing
normal routing behavior remains unchanged.

Full-board adapters validate the parsed board actually sent against the complete returned board
before lifting any additions. Entity IDs, native IDs and provenance are not geometric identity;
net and component references are resolved semantically, opaque extensions remain protected.
Copper multiplicity is preserved. SES output is a copper-only projection; all decoded copper
must pass scope checks before any selected-net filtering. No partially valid result is retained.

Task 2 is split into the immutable-delta kernel and scoped dispatch, each with its own focused
proof. Task 3 is split into process-tree cancellation and adapter budget integration. These
substeps precede CLI integration. No public option is delivered until task 4.

The existing candidate limit bounds internal shapes; each requested local adapter may add one
external alternative per subject. External decision regeneration permits the same explicit limit
and generated next commands retain it, keeping the job provenance equal across review steps.
