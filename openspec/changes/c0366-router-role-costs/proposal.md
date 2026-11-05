## Why

A short geometric path can cross switching copper or lose its ground reference. The original phase 3 requires search to account for confirmed electrical intent without inventing electrical limits.

## What Changes

Provide role-derived hard exclusions and nonnegative preference costs to search, with provenance and measured candidate facts. Preserve the existing role judge as the final authority.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routing`: electrical-role cost fields.

## Dependencies

c0365-router-search, c0222-net-roles, c0243-role-copper and c0244-critical-routes. This is 3B of the router roadmap.

## Non-goals

No fabricated creepage/current defaults, paid-standard tables, field solver, role inference changes, automatic relaxations or automatic critical-group maze routing.

## Evidence level required

Algorithmic and UI facts require `INFERRED` evidence with authored tests. Written KiCad copper
requires `KICAD-VERIFIED` on supported pinned CI targets before merge; incomplete oracle coverage
is reported explicitly. Altium readback is `INFERRED`, never native Altium validation.

## Impact

Create cli/_search_fields.py and routing/search_fields.py. The CLI orchestration layer compiles immutable role-field data into RoutingJob extras; routing reads typed values without importing roles. Extend roles/proposals.py and routing/propose.py facts. Reuse existing role/copper judges.

## Planning status

Proposed on 2026-11-03. Tasks 1–6 have passed local focused, KiCad 10.0.6 and documentation proofs; closing checks remain open. Full exact-head CI remains pending; no merge or archive is authorized. Tests named in tasks are deliverables
to create, not claims that these commands already pass. The original scope is recorded in
`docs/router-roadmap.md`; no private project is an input to this change.
