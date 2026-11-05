## Context

Fixed patterns cannot find a path around several obstacles. The original phase 3 calls for an internal search router without replacing the propose-and-lock workflow.

Original plan: archived c0222-net-roles design, sections "Plan of phases 1 to 4" and
its revised plan; c0280-route-proposals design records the deferred external candidates and
viewer drawing. See `docs/router-roadmap.md` for the inspected branch and dependencies.

## Dependencies and scope

c0228-octilinear-router and c0280-route-proposals. Add opt-in, deterministic, bounded A* search for ordinary connection subjects, including 45-degree moves and through vias. Return candidates and explicit refusals through the existing proposal contract.

## Modules and public interface

Create routing/search.py and routing/search_grid.py; extend routing/octilinear.py and routing/propose.py. Internal search(job, subject, limits) returns candidates and termination facts; it never mutates a board. Keep routing independent of roles/checks by consuming job extras and geometry callbacks.

Extend --router-option with search=off|fallback|only, search-grid=LENGTH, search-max-states=N and search-max-vias=N. Default search=off preserves existing routing. Opt-in requires explicit positive grid/state bounds and a nonnegative via bound. These options require the octilinear router and --propose, --accept or --reject; other modes return existing usage errors. Acceptance/rejection must repeat the same search and candidate options because c0280 regenerates candidates before preparing a reviewed plan. Confirmation writes the reviewed bytes without rerunning search. No new top-level command.

## Decisions

Use a sparse lattice anchored at the board origin, with exact endpoint stubs to legal pad attachment points. State includes position, layer, incoming direction and via count. Eight planar moves use integer costs and an admissible integer heuristic. Stable frontier and neighbour ordering break ties. Check swept track geometry, cutouts and diagonal corners with the existing world callbacks. Through vias require net-class diameter/drill and clearance on every copper layer crossed. Unavailable geometry or rules refuse the candidate. Existing copper stays immutable; unsupported pairs/groups retain the pattern engine or an explicit unsupported reason. Keep only completed, independently valid candidates when a budget ends. Search cost is internal, never a recommendation.

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

## Implementation clarification — 2026-11-03

The initial draft permitted search options only with --propose. Existing c0280 acceptance
regenerates candidates and does not cache their geometry. The same bounded options therefore
also apply to --accept/--reject, solely to reproduce those proposals for the reviewed decision.
No direct-routing mode or automatic acceptance is enabled.
