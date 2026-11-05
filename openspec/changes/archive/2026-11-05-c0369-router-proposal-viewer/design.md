## Context

c0280 supplies proposal data and served actions, but its design explicitly leaves drawing candidates to a later viewer change. Engineers need to inspect the actual alternatives before acceptance.

Original plan: archived c0222-net-roles design, sections "Plan of phases 1 to 4" and
its revised plan; c0280-route-proposals design records the deferred external candidates and
viewer drawing. See `docs/router-roadmap.md` for the inspected branch and dependencies.

## Dependencies and scope

c0280-route-proposals, c0303 and c0305; c0367 only for bundle-specific interaction. Render track/via alternatives with measured facts, unresolved subjects, explicit decisions and atomic bundle review in the existing shell. Keep static exports read-only and served writes under the existing plan protocol.

## Modules and public interface

Create viewer/src/proposals.ts and proposal overlay styles; connect viewer/src/main.ts and existing shell panels. Extend view/proposals.py only for missing additive scene facts, and reuse view/actions.py and view/runs.py. Regenerate committed static assets with make viewer; never edit bundles manually.

No new public CLI flag: implement the existing view --proposals and --allow-actions contract. Add viewer controls to inspect, toggle and compare candidates, review a bundle, accept/reject and inspect before/after facts. Unknown families render safe generic geometry/text with unavailable facts explicitly unknown.

## Decisions

Show subject endpoints, per-layer proposed tracks, vias, locks, relaxations, conflicts and optional reference-coverage facts. Keep current copper distinguishable without hiding unresolved/rejected subjects. Candidate order has no recommendation semantics and no preselected acceptance. Provide accessible keyboard focus and text facts, compatible with measurement and cross-probing. In a served page an acceptance first requests the existing dry-run plan; display its scope/changes, then confirm exactly that plan. Handle stale IDs and changed inputs without writing or rerunning an acceptance implicitly. Apply c0367 bundle controls only after its schema exists; independent candidate UI can land first. Static exported HTML has no write controls. Escape all board/tool/reason strings and restrict action payloads through existing allowlists. References come from pinned CI Chromium, reviewed with overlays.

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

## Implementation refinement (2026-11-03)

Keep the additive view_proposals.v0 scene; add typed contracts for endpoints, optional via drills,
locks, tool identity and bundle membership. Convert nm to whole scene micrometres using integer
ties-to-even rounding, never float division. Discard a malformed complete polyline rather than
bridging its valid points. Unknown families stay generic, unknown facts stay absent/unknown, and
untrusted strings remain data for escaped rendering. Backend slot/order/model defaults are not
UI recommendations. Shell integration uses one existing sidebar section; no shell redesign.

Served decisions need the original regeneration controls, not shell text from result.next.
Add structured controls to opt-in CLI proposal replies and the scene. The server validates a
closed field set, fixed octilinear routing, known local adapters and individual argument values;
requirements files must remain inside the project root. Never parse command strings from a
reply. Missing controls allow only legacy fixed-pattern decisions; other families remain
inspectable but unavailable for writing. Bind proposal input SHA-256 to the current board
before preview; confirmation still uses the existing staged-plan guard. Task 4 is split into
this server contract and the UI's explicit preview path before bundle-specific task 5.
