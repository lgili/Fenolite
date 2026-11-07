## Context

A short geometric path can cross switching copper or lose its ground reference. The original phase 3 requires search to account for confirmed electrical intent without inventing electrical limits.

Original plan: archived c0222-net-roles design, sections "Plan of phases 1 to 4" and
its revised plan; c0280-route-proposals design records the deferred external candidates and
viewer drawing. See `docs/router-roadmap.md` for the inspected branch and dependencies.

## Dependencies and scope

c0365-router-search, c0222-net-roles, c0243-role-copper and c0244-critical-routes. Provide role-derived hard exclusions and nonnegative preference costs to search, with provenance and measured candidate facts. Preserve the existing role judge as the final authority.

## Modules and public interface

Create cli/_search_fields.py and routing/search_fields.py. The CLI orchestration layer compiles immutable role-field data into RoutingJob extras; routing reads typed values without importing roles. Extend roles/proposals.py and routing/propose.py facts. Reuse existing role/copper judges.

No new command or electrical-limit option. Opt-in search consumes declared/confirmed roles and existing profiles. Candidate facts add reference coverage, exposure, applicable user limits and unknowns; the internal cost breakdown is diagnostic, never a score/rank/recommendation.

## Decisions

Hard electrical constraints remain geometry exclusions and cannot be traded against length. Soft preferences become nonnegative integer penalties: switching exposure and missing ground reference, never negative rewards. Derive ground coverage only from current valid poured geometry; a stale/unavailable fill is unknown, not a guaranteed plane. Missing required high-voltage distances use existing missing-limit findings. Unconfirmed inferred roles are reported but never silently promoted. Store field provenance with role/profile/board/fill fingerprints; changed inputs invalidate candidates and reviewed plans. Check completed candidates with both copper and role judges. This change applies fields to ordinary connection subjects; paired/group search remains explicitly unsupported until a separate joint-search proof exists.

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

## Implementation entry audit — 2026-11-03

- `roles.proposals.ZoneCopper` deliberately combines saved fills, simulated cells and, as a last
  resort, zone outlines for the existing proposal workflow. Its boolean `covers` result cannot
  certify a valid reference plane. Compile reference fields from the original `PourCopper.zones`
  states and validated saved geometry, retaining stale/missing/outline as unknown.
- `model.rules.NetRole.source` distinguishes declared, confirmed and inferred input. Reuse that
  distinction; do not silently turn inferred roles into routing constraints with confirmed status.
- `roles.profile.resolve` supplies existing scoped limits and provenance. A missing high-voltage
  distance must remain missing, rather than borrowing the switching-distance profile default.
- `routing.search` already owns integer moves and exact geometry; `routing.search_grid.astar`
  accepts integer edge costs and a lower bound. Add fields through an immutable job extra,
  leaving the routing package independent of `roles` and `checks`. New penalties may increase
  cost but must not make the existing geometric lower bound overestimate a legal remaining path.
- Reuse the job's copper/role judgment callbacks on completed candidates and include every actual
  board, role/profile and fill input in changed-input protection, not merely a displayed hash.


## Concrete interchange and CLI clarification — 2026-11-03

`routing.search_fields` defines frozen `Provenance`, `Spacing`, `Influence`, `Copper`, `Ground`
and `Fields` packets. Only validated saved-fill polygons enter `Ground`. Unknown reference
information stays separate. Packet identity hashes logical data, excluding acceleration caches.
Hard distances and soft influences are nonnegative integer nm; internal preferences add costs,
never rewards. Confirmed reference length is a conservative lower bound: only complete swept
segments contained in validated ground copper count; remaining length is unconfirmed, not an
assertion that it is physically uncovered. Unknown reference gets no certainty or negative reward.

The existing route command has no requirements-file input. Reuse the established `--requirements
FILE` contract of `copper`/`analyze` for opt-in search proposal and decision modes; no new numerical
electrical-limit flag or value is introduced. Load the same TOML schema and include its file in
reviewed-plan dependencies. Other route modes reject this input rather than silently ignore it.
This small CLI extension and its tested guide line belong to tasks 4 and 6.

## Layer-boundary correction — 2026-11-03

The first complete quick gate exposed the existing `roles → routing` prohibition. Keep that
architecture rule unchanged: the compiler belongs in `cli/_search_fields.py`, which is the allowed
orchestrator of roles, current-fill analysis and routing geometry. It produces the frozen
`routing/search_fields.py` packet. Roles and routing retain their existing package boundaries;
neither imports the other. Task 2's immutable compilation behavior and its proof remain unchanged.
