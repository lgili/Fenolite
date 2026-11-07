## Why

Independent paths can consume the only corridor available to another net. The original phase 3 includes bounded negotiation across nets, beyond repeating fixed patterns.

## What Changes

Negotiate provisional routes for selected subjects in private memory and present jointly valid alternatives as atomic bundles. Protect manual copper, existing decisions and electrical corridors.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routing`: negotiated congestion and atomic reroute bundles.
- `agent-guide`: a dedicated route-proposals page within the existing page-size budget.

## Dependencies

c0365-router-search, c0366-router-role-costs and c0280-route-proposals. This is 3C of the router roadmap.

## Non-goals

No ripping manual/locked copper, accepting provisional overlaps, silently accepting an alternative, global optimality claim or automatic pair/group constraint relaxation.

## Evidence level required

Algorithmic and UI facts require `INFERRED` evidence with authored tests. Written KiCad copper
requires `KICAD-VERIFIED` on supported pinned CI targets before merge; incomplete oracle coverage
is reported explicitly. Altium readback is `INFERRED`, never native Altium validation.

## Impact

Create routing/negotiate.py and routing/bundles.py; extend routing/protocol.py, routing/decisions.py, routing/propose.py and cli/_propose.py. negotiate(job, subjects, limits) is internal. Add additive bundle membership/fingerprints to the decision and proposal contracts; older independent candidates remain readable.

## Planning status

Proposed on 2026-11-03. Tasks 1–6 have passed focused local proofs, including native KiCad 10.0.6 and 55 guide tests. The full local quick gate passes; exact-head CI closing evidence remains pending. The original scope is recorded in
`docs/router-roadmap.md`; no private project is an input to this change.
