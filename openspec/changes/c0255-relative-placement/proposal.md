## Why

A Fenolite script places a part only by absolute board coordinates (`u1.place(mm(14), mm(15), rot=90)`).
To put a decoupling capacitor next to a pin, the author computes the pin's position by hand and redoes
it whenever the IC moves. `design.near()` is checked, never applied. Layout strategies exist only as CLI
steps over a built board (`fenolite place --strategy grid|region|reuse`). A block of c0251 cannot be
moved as a whole, cannot arrange its own parts, and cannot bring a layout of its own.

The research of 2026-10-29 (`docs/research/circuit-as-code.md`, section 10, core change I) found the
missing ideas in tscircuit (positions relative to parts, pads and the board edge; layouts per group),
JITX (placement relative to the parent block, which makes the block a rigid group) and atopile (a package
that ships its own laid-out sub-board). tscircuit leaves the precedence of these sources unwritten
("TODO"); Fenolite writes it down.

## What Changes

- **Relative `place()`.** `Part.place()` accepts references besides `x, y`: `right_of`, `left_of`,
  `above`, `below` with `gap` and `align`; edge keys `left`, `right`, `top`, `bottom`, `center_x`,
  `center_y` taking a length or an edge expression (`board.left + mm(2)`, `u1.right`,
  `u1.pad("VDD").center_y`); and `by=part.pad(n)`, which positions the part by one of its pads. The
  references are parts, pads, block instances and the board. The build resolves every request to integer
  nanometres and records each resolution.
- **Block pose and rigid group.** A c0251 block instance gets `inst.place(...)` (absolute or relative):
  the children's placements are in the block's frame and move with it. When a block's pose changes, its
  children kept from the board move rigidly with their copper (c0227's group rules).
- **Layout strategies per block.** `row(...)`, `column(...)`, `grid(...)` and `pack(...)` arrange the
  block's parts that no other source places, deterministically, in the block frame (`b.layout(...)` in the
  body, `inst.layout(...)` per instance, `design.layout(...)` at the top).
- **Block layout reuse.** `b.layout(reuse="buck.kicad_pcb", copper=True)` places a block's parts, and
  optionally its copper, from a board laid out for the block alone, through c0210/c0227's per-part fit and
  copper copy; parts map by block path and nets by port, never by majority vote.
- **Documented precedence**: (1) locked `place()`; (2) the board; (3) the placements file; (4) unlocked
  `place()`, absolute or relative; (5) the block strategy or reuse; (6) staging.

## Capabilities

### New Capabilities

- `placement-in-code`: resolution of relative requests, measuring boxes, order, recording, block poses and
  rigid moves, the four strategies, groups without a pose, and the `layout.relative-*` and block codes.

### Modified Capabilities

- `design-dsl`: ADDED "Relative placements in the DSL", "Placement references", "Axis determination",
  "Locked relative placements", "Block poses in the DSL", "Layout strategies in the DSL", "Block layout
  reuse in the DSL".
- `layout-lens`: MODIFIED "Placement precedence" (six levels; relative requests, block poses and
  strategies).
- `layout-reuse`: ADDED "Block layout reuse in a build", "Nets mapped by port", "Block reuse codes".

## Dependencies

c0251 (blocks, instances, ports, block paths) is required for poses, strategies and reuse; relative
`place()` of plain parts needs nothing new. Reuses c0210/c0227 (fit, copper copy, group moves) and the
layout lens. c0250 (`edits.toml`) is level 3 of the precedence once it lands. Implementation step 6,
with c0254; independent of it.

## Non-goals

- No optimising placer, no overlap solver: a relative request is resolved exactly as written, and the
  legality check of the build reports what overlaps.
- No mirrored block pose (`side="bottom"` for a whole block) in this change (open question).
- No expressions beyond an edge plus or minus a length; no arithmetic between two references.
- `near()` stays a checked rule; it does not place.

## Evidence level required

- Resolution, strategies and precedence: `INFERRED`, proven by unit tests on authored designs.
- Built boards: `KICAD-VERIFIED` read-back that every footprint lies where the resolution says, on
  targets 9 and 10.
- Block layout reuse: `INFERRED` as c0210's reuse without `--drc`; `fenolite check` judges the result.

## Impact

- New: `src/fenolite/placement/relative.py`, `src/fenolite/placement/strategies.py`,
  `src/fenolite/dsl/relative.py`, `examples/relative/`.
- Changed: `dsl/part.py` (`place`), `dsl/design.py` (`board` returns a `BoardRef`, `layout`), c0251's
  block instance, `lens/preserve.py` (`effective_placements`), `cli/cmd_build.py`, `reuse/fit.py` and
  `reuse/copper.py` (explicit transform and net map), `explain.toml`, `docs/dsl.md`, `docs/lens.md`,
  `docs/placement.md`, guide pages `placement` and `board-floorplan`.
- Size: about 10 design-days.
