## Why

A script can declare 2 or 4 copper layers only: `design.board(copper=6)` raises `DslError`, and the KiCad layer table (`created_layers`), the build and the rebuild repeat the limit (`origin/dev` at `9aba2dff`; the places are listed in the design). The review of 2026-10-05 of the gaps to a complex board asks for 4 to 8 layers; its proposals are milestone v0.4 (`docs/roadmap.md`, "v0.4: proposals on other branches"). The model, the reader and the writer have no such limit, and since c0085 the Altium build has none either: its stack takes any even count up to 32, so the guard in the script is the only thing that keeps a design at 2 or 4.

Probes on `kicad-cli` 10.0.6 and 9.0.9 (2026-10-05, on the branch where this proposal was written; not repeated on `dev`):

- Created tables of 6 and 8 copper layers, numbered as KiCad's own demos, load on both majors, export one Gerber per copper layer and survive a re-save on 10.0.6.
- With the guards lifted in-process, builds of 4, 6 and 8 layers for both targets fill every inner zone, pass DRC with no violation or unconnected item, export, and rebuild to the same bytes; 9.0.9 gives the same report on the filled target-9 boards.
- Tables of 3 and 5 copper layers are refused by both majors.

## What Changes

- **Counts.** `design.board(copper=n)` takes n = 2, 4, 6 or 8; other values raise `DslError`. `layers.created_layers(n)` adds one row `(2k + 2, "In<k>.Cu", signal)` per inner layer.
- **Inner layers.** `zone(layers=…)` and `planes=` take every inner layer of the count; `Design.copper_layers` lists them.
- **Planes on KiCad.** Still not written; the `build.plane-not-lowered` hint names `design.zone(…)`, not the KiCad editor.
- **Rebuild.** Six and eight layers keep their layout as 2 and 4 do. Another count still gives `layout.copper-mismatch`, whose hint names `copper=m` when the board holds Fenolite's table of an allowed count m.
- **Altium.** A script of 6 or 8 layers gets its PCB document through the stack that c0085 writes (`altium-pcb-writer`, "Layer stacks of any even count"): planes, zones and script copper on every inner layer. No record is added. `STACK_HINT` stops naming `copper=2` and `copper=4` as the only counts.
- **Oracle.** Table probes on both majors; builds of 4, 6 and 8 layers through fill, DRC and export on 10.0.6; DRC and export of filled target-9 fixtures on 9.0.9.

Size: 3.5 design-days; cut order in the design.

## Prerequisites

- Release 0.3.0 is out, with c0085 archived: the Altium requirement of this change is worded on c0085's "Layer stacks of any even count", "Copper issue codes" and "Complete board in an Altium build".
- c0096 (implemented on its own branch) also modifies "Board and placements in the DSL" (`anchor=` on `Part.place` and `Placement`). Either order works; the one that lands second regenerates its delta from the living text. c0097 and c0099 are not touched.
- Of the v0.4 proposals none must land before this one. It lands first in its group: c0101, c0102, c0103, c0105, c0107, c0112, c0115 and c0119 build on its counts (order per shared requirement in the design, Decision 7).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-dsl`: MODIFIED "Design structure and names", "Board and placements in the DSL", "Zones in the DSL", "Planes in a build"; ADDED "Copper layer counts in a build".
- `kicad-file-backend`: MODIFIED "Created board header".
- `layout-lens`: ADDED "Layer count across rebuilds".
- `altium-build`: ADDED "Script layer counts in an Altium build".
- `kicad-oracle`: ADDED "Created layer tables are probed on both majors", "Builds of four, six and eight copper layers pass the oracle".

## Non-goals

- No count above 8: nowhere for now, because no yardstick board needs one; both majors load up to 34 (open question).
- No odd count: nowhere, because both majors refuse it.
- No stack-up: c0101; the job file states KiCad's default.
- No plane written to KiCad (a zone, or the row type `power`): c0107 decides whether routing needs a marker.
- No layer-count change that keeps the layout: c0102.
- No routing on 6 or 8 layers: c0107 and c0109.
- No Altium record, layer id or format fact: c0085 owns the stack of the PCB document, and this change adds none.
- No proof of blind, buried and micro vias above 4 layers: nowhere, because their span check does not depend on the count.

## Evidence level required

- New rows `H-K-PCB-LAYERS` and `H-K-BUILD-LAYERS`, settled by probes on 9.0.9 and 10.0.6 before merge; the re-save runs on 10.0.6 only, as 9.0.9 has no `pcb upgrade`.
- Counts, inner names and hints are mechanical: unit scenarios. The Altium document of 6 or 8 layers rests on c0085's stack and its evidence, which this change does not raise.

## Impact

- Changed: `dsl/design.py`, `backends/kicad/layers.py`, `lens/build.py`, `lens/preserve.py`, `lens/altium_copper.py` (one hint), `cli/cmd_build.py`, `cli/data/explain.toml` (two `fix` texts), three test fixtures, four documentation pages.
- New: table and build oracle tests, two filled target-9 fixtures (declared in `tests/data/MANIFEST.toml`).
- No model key and no issue code is added.
- c0101 regenerates "Created board header" on the text this change leaves.
