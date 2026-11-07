## Why

c0280 explicitly deferred --propose-with. Existing external routers can route a job, but they do not yet supply reviewable, isolated candidates in the proposal workflow.

## What Changes

Adapt locally available external routers into candidate generators using existing subprocess adapters, shared budgets, strict board-delta validation and the same measured facts as internal candidates.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routing`: external-router proposal candidates.

## Dependencies

c0280-route-proposals and the existing routing plugin/budget contracts (c0016, c0023, c0109). This is 4 follow-up of the router roadmap.

## Non-goals

No automatic downloads, cloud uploads, bundled router code, GPL imports, replacing existing route commands or automatically selecting an external candidate.

## Evidence level required

Algorithmic and UI facts require `INFERRED` evidence with authored tests. Written KiCad copper
requires `KICAD-VERIFIED` on supported pinned CI targets before merge; incomplete oracle coverage
is reported explicitly. Altium readback is `INFERRED`, never native Altium validation.

## Impact

Create routing/external_candidates.py and extend routing/propose.py, routing/select.py and cli/_propose.py. Reuse existing adapters and routing/budget.py; do not create a second external process stack. An internal generate_external(job, subjects, routers) returns validated candidates or explicit refusals.

## Planning status

Proposed on 2026-11-03. No implementation task is complete. Tests named in tasks are deliverables
to create, not claims that these commands already pass. The original scope is recorded in
`docs/router-roadmap.md`; no private project is an input to this change.
