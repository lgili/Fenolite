## Why

Fixed patterns cannot find a path around several obstacles. The original phase 3 calls for an internal search router without replacing the propose-and-lock workflow.

## What Changes

Add opt-in, deterministic, bounded A* search for ordinary connection subjects, including 45-degree moves and through vias. Return candidates and explicit refusals through the existing proposal contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routing`: bounded multilayer search.

## Dependencies

c0228-octilinear-router and c0280-route-proposals. This is 3A of the router roadmap.

## Non-goals

No independent pair routing, critical-group relaxation, placement, length tuning, blind vias, native acceleration or automatic acceptance.

## Evidence level required

Algorithmic and UI facts require `INFERRED` evidence with authored tests. Written KiCad copper
requires `KICAD-VERIFIED` on supported pinned CI targets before merge; incomplete oracle coverage
is reported explicitly. Altium readback is `INFERRED`, never native Altium validation.

## Impact

Create routing/search.py and routing/search_grid.py; extend routing/octilinear.py and routing/propose.py. Internal search(job, subject, limits) returns candidates and termination facts; it never mutates a board. Keep routing independent of roles/checks by consuming job extras and geometry callbacks.

## Planning status

Proposed and implementation started on 2026-11-03. See tasks.md for passed focused proofs;
closing validation remains open. Unchecked tasks are not claims of passing proof. The original scope is recorded in
`docs/router-roadmap.md`; no private project is an input to this change.
