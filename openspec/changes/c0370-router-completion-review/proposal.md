## Why

Finishing algorithms is not proof of a usable board workflow. The original study also asks for regional review, preservation of locked edits and checked KiCad/Altium output. Those obligations need explicit, reproducible acceptance work.

## What Changes

Document and exercise the complete reviewed workflow, truthful completion reporting, scoped tidy, lock preservation and authored two/four-layer acceptance/scale fixtures. Separate implementation order from per-board execution order.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `routing`: router workflow completion and acceptance evidence.

## Dependencies

c0365 through c0369 for final acceptance; existing c0222/c0243/c0244/c0280 for early documentation. This is cross-cutting acceptance (not a phase 5) of the router roadmap.

## Non-goals

No one-click silent autoroute, manufacturing certification, guessed safety limits, private reference boards, direct Altium edit sessions (c0241), arbitrary size guarantee or a newly invented numbered phase.

## Evidence level required

Algorithmic and UI facts require `INFERRED` evidence with authored tests. Written KiCad copper
requires `KICAD-VERIFIED` on supported pinned CI targets before merge; incomplete oracle coverage
is reported explicitly. Altium readback is `INFERRED`, never native Altium validation.

## Impact

Extend docs/roles.md and docs/router-roadmap.md; add docs/evidence/router-completion.md, examples/routing/ authored generators and focused acceptance tests. Reuse existing CLI stages, checks, tidy and convert. If existing reports lack unresolved/rejected distinctions, extend cli/_propose.py result facts additively, not with a new command.

## Planning status

Proposed on 2026-11-03. No implementation task is complete. Tests named in tasks are deliverables
to create, not claims that these commands already pass. The original scope is recorded in
`docs/router-roadmap.md`; no private project is an input to this change.
