## Context

Finishing algorithms is not proof of a usable board workflow. The original study also asks for regional review, preservation of locked edits and checked KiCad/Altium output. Those obligations need explicit, reproducible acceptance work.

Original plan: archived c0222-net-roles design, sections "Plan of phases 1 to 4" and
its revised plan; c0280-route-proposals design records the deferred external candidates and
viewer drawing. See `docs/router-roadmap.md` for the inspected branch and dependencies.

## Dependencies and scope

c0365 through c0369 for final acceptance; existing c0222/c0243/c0244/c0280 for early documentation. Document and exercise the complete reviewed workflow, truthful completion reporting, scoped tidy, lock preservation and authored two/four-layer acceptance/scale fixtures. Separate implementation order from per-board execution order.

## Modules and public interface

Extend docs/roles.md and docs/router-roadmap.md; add docs/evidence/router-completion.md, examples/routing/ authored generators and focused acceptance tests. Reuse existing CLI stages, checks, tidy and convert. If existing reports lack unresolved/rejected distinctions, extend cli/_propose.py result facts additively, not with a new command.

No new command. Publish a review recipe using capabilities, confirmed roles, critical routes, power copper, proposals/acceptance, fill, check, export and render. Any tidy is explicitly scoped, separately reviewed and followed by checks. Document current options and result fields in tested guide lines.

## Decisions

Development order remains 0->1->2->4->3; per-board canonical order is confirmed roles -> critical routes -> power copper -> propose/review/accept -> optional tidy -> fill -> check -> export. A second run preserves locks and manual edits. Completion requires post-fill connectivity and required electrical/DRC checks; distinguish physical opens, rejected alternatives, not-attempted subjects and unknown checks. Never equate proposed/rejected/unavailable with connected. Retain baseline findings and oracle version. On KiCad targets with reduced oracle support, report those limits rather than a false zero-open claim. Validate KiCad output then convert to Altium and compare locked route/net/layer identity by readback; evidence stays INFERRED until native validation. Use authored 2/4-layer generators with up to about 150 parts, fixed seeds, expansion/round/candidate counters and separate wall-clock telemetry. Set documented performance thresholds only from recorded measurements. Whole-flow runs are sequences of reviewed transactions, not falsely atomic global writes.

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
