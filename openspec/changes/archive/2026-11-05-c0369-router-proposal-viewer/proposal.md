## Why

c0280 supplies proposal data and served actions, but its design explicitly leaves drawing candidates to a later viewer change. Engineers need to inspect the actual alternatives before acceptance.

## What Changes

Render track/via alternatives with measured facts, unresolved subjects, explicit decisions and atomic bundle review in the existing shell. Keep static exports read-only and served writes under the existing plan protocol.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `board-viewer`: visible routing proposals in the engineering viewer.

## Dependencies

c0280-route-proposals, c0303 and c0305; c0367 only for bundle-specific interaction. This is 4 follow-up of the router roadmap.

## Non-goals

No new editor, automatic candidate choice, recommendation score, arbitrary shell execution, server bypass or native desktop framework.

## Evidence level required

Algorithmic and UI facts require `INFERRED` evidence with authored tests. Written KiCad copper
requires `KICAD-VERIFIED` on supported pinned CI targets before merge; incomplete oracle coverage
is reported explicitly. Altium readback is `INFERRED`, never native Altium validation.

## Impact

Create viewer/src/proposals.ts and proposal overlay styles; connect viewer/src/main.ts and existing shell panels. Extend view/proposals.py only for missing additive scene facts, and reuse view/actions.py and view/runs.py. Regenerate committed static assets with make viewer; never edit bundles manually.

## Planning status

Proposed on 2026-11-03. No implementation task is complete. Tests named in tasks are deliverables
to create, not claims that these commands already pass. The original scope is recorded in
`docs/router-roadmap.md`; no private project is an input to this change.
