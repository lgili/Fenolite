## Why

A part without `place()` is staged in a row beside the outline (c0011), and only the script or the KiCad editor can bring it onto the board. Nothing tells the author, before a board is written, that two courtyards overlap or that a part hangs over the edge: the dogfood buck board found both by hand, and got the 270° case wrong. v0.1's loop needs `place` (plan D11: `manual` and `grid` placement), and the roadmap adds the legality check to this change.

c0019 made the board the layout authority and left the placer a slot in its precedence: a placer "moves staged parts onto the board, after which the board placement wins". c0028 gives placed courtyards in the board frame (`BoardFrame.placed_extents`). A translation only changes a footprint's position; a new rotation or side re-places it from its library definition, as c0019 already does for a locked `place()`.

## What Changes

- `placement/` (new package): `legality` (courtyard overlap, outside the outline, edge clearance, with the exact kernel), `grid` (a deterministic shelf placer for staged parts) and `manual` (explicit moves).
- `backends/kicad/replace.py` (new): `move_footprint` translates a footprint of a read board, or re-places it from its library definition for a new rotation or side, keeping uuid, fields, properties, pad nets and lock; without a definition, a rotation or side change is refused.
- `backends/kicad/outline.py` (new): the board outline as rings, from the model outline or from `Edge.Cuts` graphics, chained exactly.
- `fenolite place PATH --strategy grid|manual` (new, mutating): edits the board; refuses to write an illegal placement unless `--force`.
- `build`: the legality check runs on the layout before the plan is returned and reports `place.*` warnings; it never refuses a build.
- Probes first on 9.0.9 and 10.0.6: a moved footprint's position, rotation and side through `pcb export pos`; its pad nets through IPC-D-356; touching courtyards against KiCad's `courtyards_overlap`.
- Hypotheses `H-K-PLACE-MOVE`, `H-K-PLACE-TOUCH`, `H-G-PLACE-OUTLINE`.

Budget: 6.0 days against the roadmap's 4.5; the cut order is in the design.

## Capabilities

### New Capabilities
- `placement`: legality, the grid and manual strategies, issue codes, evidence.

### Modified Capabilities
- `kicad-file-backend`: ADDED "Footprints are re-placed on a read board", "Board outline as rings".
- `design-dsl`: ADDED "Placement legality in a build".
- `kicad-oracle`: ADDED "Moved footprints pass the oracle".
- `cli-contract`: ADDED "Place command".

## Non-goals

- An optimising placer (annealing is v0.5a); placement by net length, by module or by constraints.
- Moving tracks, vias or zones with a part; ripping up copper.
- A `check` stage: KiCad's DRC already reports `courtyards_overlap`, and c0020 maps it to an issue.
- Silkscreen and field legality (c0030's canaries); copper clearance (c0029).
- A snapping tolerance for outlines: chaining stays exact (`H-G-EDGE-EXACT`, c0020).
- `placements.toml` and the full layout lens (v0.2b).

## Evidence level required

- Legality geometry: mechanical (exact integer kernel); overlap semantics for touching courtyards `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-PLACE-TOUCH`), reusing `H-G-FRAME-CRTYD` for the extents.
- Re-placed footprints: `KICAD-VERIFIED (9.0.x, 10.0.x)` for position, rotation, side and pad nets (`H-K-PLACE-MOVE`).
- Outline from `Edge.Cuts`: `CORPUS-VERIFIED` once every readable demo board assembles or names its problem (`H-G-PLACE-OUTLINE`), reusing `H-G-EDGE-EXACT`.
- Grid placer and the command: mechanical (hermetic tests); results carry `INFERRED`, because KiCad's DRC is the judge.

## Impact

- New `placement/`, `backends/kicad/{replace,outline}.py`, `cli/cmd_place.py`; extended `lens/build.py` and `cli/cmd_build.py`.
- No runtime dependency, model or schema change; the `placement` row of `package-layering` already exists.
- Depends on c0019 (archived), c0028 (`BoardFrame`) and c0030 (field placement on re-placed footprints), which archive first; c0020's Edge.Cuts census informs the outline (by order only).
