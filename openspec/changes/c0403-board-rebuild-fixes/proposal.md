# c0403: Fenolite bugs found by a private board rebuild

## Why

On 2026-11-04/05 an agent rebuilt a private board as Fenolite design code and recorded the Fenolite issues
it met as F1–F11 in a private report. The board and the report stay outside the repository; nothing of the board is
copied here. Each fix below is proven on an authored fixture that has the shape of the bug, never the
board's data.

## What

One task per Fenolite bug:

| id | bug | fix |
|---|---|---|
| F2 | `rules.minimum(netclass=)` governs every custom rule of that class without `priority=`, and the docstring of `minimum()` did not say so | the docstring and the guide page `board-insulation` say it and name `precedence("specificity")`; a test proves both orders |
| F3 | a part-wide pad-gap rule is a minimum for all pad pairs of the part, and no page showed how to write an exception between two domains inside one part | the guide page shows the per-domain form; a test resolves both forms |
| F4 | the net of a no-connect pin has no class, so a class exception does not reach it | the guide page says it is in `Default` and is reached by its part; a test resolves it |
| F5 | `fenolite check` of an imported project ended with `FEN-1001` on a circular pad of size 0, reached through the `rules.shadowed` pass | fixed on `dev` by c0364 (`model_pads` leaves such a pad without copper); c0403 adds the regression test through the shadowed-rule pass. A private rerun on 1169f10d exits 5, as before the regression, instead of 1 |
| F6 | `fenolite route --router freerouting` plans copper narrower than the governing track-width rule (Freerouting narrows wires) | the routed copper is judged against the governing `track_width` rule; copper below it is an error, so no write is planned |
| F7 | dry-run plans live in one store for the machine, and its count of 16 is shared by every project, so other projects' dry runs drop a plan under review | the count is per working folder, with a bound of 128 plans in all; the contract text says how long a plan is kept and how to keep a long review apart |
| F8 | the Specctra export combines clearance rules by maximum, so a higher-priority, lower pair rule is lost, and a class never goes below its own clearance against itself; nothing warns | the rules are lowered in precedence order, the governing rule sets each pair, a self rule may lower a class against itself, and a value kept above the governing rule gives `specctra.rule-widened` |
| F9 | the build's copper check does not judge copper against drilled holes (unplated holes and slots of footprints included) | a `copper.hole-clearance` finding against the board's minimum hole clearance |
| F10 | the build accepts script copper narrower than the governing track-width rule | the build's copper guard reports `copper.track-width` (error) |

F1 (clockwise catalog lands hidden by a waiver) is fixed and archived by c0385.

### Not here

| id | item | owner |
|---|---|---|
| F11 | the octilinear router leaves most connections of a dense board open (it tries a few shapes per connection) | the router track (a follow-up change of c0365–c0370). It is a coverage limit that the report itself names as such. The case needs a public board of that density to be reproduced; the private board was routed by other means and no longer holds the open state |
| — | the footprints and symbols the rebuild had to author because the catalog lacks them | `fenolite-library` (github.com/lgili/fenolite-library), each item drawn from a public source with its licence and `PROVENANCE.json` |
| — | the defects of the original board's own design | the board's owner; not Fenolite |
| — | the private grid A* script and the hand copper of the rebuild | the private project; not Fenolite |

## Impact

`checks/copper.py` (hole clearance), a new width check used by `build` and `route`, `backends/specctra/dsn.py`,
`cli/plans.py`, the docstring of `design.rules.minimum`, the guide page `board-insulation`,
`docs/cli-contract.md`, `docs/formats/specctra/dsn.md` and the copper and width codes with their `explain`
entries. Builds and routes that held narrow copper or copper too close to a hole now report an error and plan
no write. No model field or evidence level is raised; the new rows are `INFERRED`.

## Follow-ups found on 2026-11-05

- The Altium writer sets each `Width` rule's `MINLIMIT` to the narrowest copper it writes, not to the
  design's minimum, so an Altium build never reports narrow copper (outside F10).
- `route`, `tidy`, `place` reuse and the placement checks call `check_copper` without the hole clearance,
  so they do not judge copper against holes yet (outside F9).
