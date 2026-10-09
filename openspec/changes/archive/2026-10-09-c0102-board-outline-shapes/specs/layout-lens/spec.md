## ADDED Requirements

### Requirement: Outline changes across rebuilds
`fenolite.backends.kicad.outline.merge_outline(built, board, *, locked=False) -> OutlineMerge` SHALL decide whether a rebuild keeps the existing board's edge content or replaces it with the built outline, and `lens.preserve.merge_layout(…, lock_outline=…)` SHALL adapt the existing board with its result, passing `lock_outline` as `locked`, before the other rules of "Board content outside the design is kept".
- The edge content is the board's root `Graphic`s on layers of kind `edge`. It is *signed* when it holds at least one graphic, every graphic is a `line` or an `arc`, and the KiCad uuid of each equals `pcb.kicad_uuid(<built outline>, "outline:<digest>:<its edge text>")`, where the digest is `outline_digest` of the edge texts of all of them (`kicad-file-backend`, "Outline lowering"). A signed content is one that Fenolite wrote and that nobody changed since: a move in KiCad keeps the uuid and changes the text.
- With the built outline compared as edge texts, the cases MUST be:

| the board's edge content | compared with the built outline | result |
|---|---|---|
| none | — | unchanged: the built outline is used, as today |
| any | equal | kept; when every uuid is the position uuid `pcb.kicad_uuid(<built outline>, "outline:<ring>:<edge>")` of an older Fenolite, re-signed |
| signed | different | replaced, `kicad.outline.replaced` |
| not signed | different, `locked` true | replaced, `kicad.outline.forced` |
| not signed | different, `locked` false | kept: "Board content outside the design is kept" gives `layout.outline-kept` |

- *Replaced* and *re-signed* mean that the adapted board has none of its edge graphics and has the built outline as its `Board.outline`, which the writer then emits signed.
- When the content is replaced, each track, arc and via of the board that is not script copper (`manual-copper`, "Script copper is regenerated") and does not fit the new board MUST be dropped. An item fits when its copper, the core widened by half its width or a via's disc as `geometry.Thick`, touches no ring of `board_outline` of the built design and its first core point lies inside the board ring and outside every cut-out (`thick_touch`, `point_in_ring`). One `kicad.outline.copper-dropped` MUST give the counts of tracks, arcs and vias dropped and their nets.
- When the content is replaced, a board zone whose KiCad uuid is that of a built zone MUST take the built zone's outline when its own outline is the box of the replaced board ring and the built zone's is the box of the built one; the box of a board ring is the rectangle of its vertices and arc mid points that a zone declared without an outline takes (`design-dsl`, "Zones in the DSL"). Such a zone was declared without an outline and follows the board; "Zones declared in the script" then finds the two equal.
- Edge items inside footprints (`frame.footprint_edges`, `H-K-OUTLINE-FPEDGE`), which "Board outline as rings" chains into the outline, are not edge content of this requirement: they belong to their footprints, which the script does not draw. They MUST NOT be signed, compared, replaced or removed, and the table above reads the root graphics alone. A kept footprint keeps them ("Kept and re-placed footprints"). When the root content is replaced and a footprint of the board holds an edge item, the message of `kicad.outline.replaced` or `kicad.outline.forced` MUST name those footprints, because their edge items stay in the new outline. A board whose outline closes only with footprint edge items has no signed content: its root graphics follow the rows "not signed".
- Footprints MUST NOT move: the placement guard names those that the new outline leaves out. Fills are judged by "Zone fills and the staleness digest", whose digest holds the edge content.
- `OutlineMerge` is a frozen dataclass with `board` (the adapted board design), `replaced`, `dropped` (counts by kind) and `issues`. `merge_outline` reports only the codes of the closed table `outline.MERGE_ISSUE_CODES`; they are `kicad.*` codes, so they pass `PRESERVE_ISSUE_CODES` and `BUILD_ISSUE_CODES` unchanged.

| code | severity | when |
|---|---|---|
| `kicad.outline.forced` | warning | a locked `board()` replaced edge content that is not Fenolite's unchanged outline |
| `kicad.outline.copper-dropped` | warning | tracks, arcs or vias that do not fit the new outline were dropped |
| `kicad.outline.replaced` | info | the board's own unchanged outline was replaced by the script's new one |

#### Scenario: An unchanged outline follows the script
- **GIVEN** a confirmed target-10 blink build whose board was edited by `edit_blink`, after which `design.py` declares `board(mm(60), mm(30))`
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the written edges are the 60 mm × 30 mm rectangle with the uuids of "Outline lowering", the segments and the via of the edit are kept, and `issues` holds `kicad.outline.replaced` and no `layout.outline-kept`

#### Scenario: Copper that no longer fits
- **GIVEN** a confirmed target-10 blink build whose board gets, by token edit, a segment on `GND` from (110 mm, 128 mm) to (120 mm, 128 mm) and another from (145 mm, 105 mm) to (148 mm, 105 mm), after which `design.py` declares `board(mm(40), mm(30))`
- **WHEN** the build runs again with `--confirm`
- **THEN** the first segment is written and the second is not, and `issues` holds one `kicad.outline.copper-dropped` naming 1 track on `GND`

#### Scenario: An edited outline wins unless locked
- **GIVEN** a confirmed blink build whose right `Edge.Cuts` line is moved 5 mm right, with the top and bottom lines lengthened to meet it, by token edit, after which `design.py` declares `board(mm(60), mm(30))`
- **WHEN** the build runs again with `--confirm`, and once more with `board(mm(60), mm(30), locked=True)`
- **THEN** the first writes the edited lines with `layout.outline-kept`, and the second writes the 60 mm × 30 mm rectangle with `kicad.outline.forced`

#### Scenario: A re-save keeps the signature
- **GIVEN** a confirmed target-10 build of the rounded board of `design-dsl` "Outline shapes in a build", re-saved by `kicad-cli pcb upgrade --force`
- **WHEN** `design.py` changes the radius to 3 mm and the build runs again
- **THEN** the outline is replaced, with `kicad.outline.replaced`

#### Scenario: A zone without an outline follows
- **GIVEN** a confirmed build of the blink pour variant, whose zone `GND` has no outline, after which `design.py` declares `board(mm(60), mm(30))`
- **WHEN** the build runs again
- **THEN** the zone's outline is the 60 mm × 30 mm rectangle, and `issues` holds no `kicad.zone.overridden`

#### Scenario: Edges of an older Fenolite
- **GIVEN** a blink board whose four edge lines carry the uuids `pcb.kicad_uuid(outline, "outline:0:<k>")`
- **WHEN** it is rebuilt with its own outline, and in a copy with `board(mm(60), mm(30))`
- **THEN** the first writes the same lines with the uuids of "Outline lowering", and the second keeps the old lines with `layout.outline-kept`

#### Scenario: Edge items of a footprint stay
- **GIVEN** a confirmed target-10 blink build whose board gets, by token edit, an `fp_rect` of 2 mm × 1 mm on `Edge.Cuts` inside the footprint of `U1`, after which `design.py` declares `board(mm(60), mm(30))`
- **WHEN** the build runs again with `--confirm`
- **THEN** the root edges are the 60 mm × 30 mm rectangle, `issues` holds one `kicad.outline.replaced` that names `U1`, the `fp_rect` is still in the footprint of `U1`, and `board_outline` of the written board gives two rings

### Requirement: Copper layer changes across rebuilds
`fenolite.backends.kicad.layers.merge_layers(board, copper) -> LayerMerge` SHALL adapt an existing board whose copper layer names are those of `layers.created_layers` for another count, the count that c0100's `layers.created_count(<names>)` gives, to the copper layers of `created_layers(copper)`; `lens.preserve.merge_layout` SHALL adapt the board with it first, before "Outline changes across rebuilds" and every other rule.
- The rows of the layers that stay MUST keep their `kicad` bags, with the type and user name set in KiCad. The rows of new inner layers MUST be those of `created_layers(copper)`; the rows of removed layers MUST go. A smaller count removes the deepest inner layers, `In<copper − 1>.Cu` and below.
- On a removed layer: tracks and arcs MUST be dropped; a via whose `layers` name the layer MUST be dropped, and a through via kept; zones and rule areas MUST lose the layer, and be dropped when none is left, fills of that layer included; root graphics and texts on it MUST be dropped. One `kicad.layers.removed` per removed layer MUST give the counts. KiCad would load these items and report `item_on_disabled_layer` (`H-K-LAYER-CHANGE`).
- Every pad of a kept footprint whose `layers` child holds a wildcard MUST take the layers that the wildcard gives on the new table, copper layers first in table order, so the writer's projection check accepts it.
- A `stackup` child of the board's `setup` whose copper layers are not those of the new table MUST be removed, with `kicad.layers.stackup-reset`, so that KiCad derives its default stack-up for the new count; a stale one leaves the Gerber job file without thicknesses (`H-K-LAYER-CHANGE`). `Board.stackup` of the adapted board, the value the reader projected from that child (`kicad-file-backend`, "Stack-up on boards"), MUST then be `None` whenever its copper entries are not the copper layers of the new table: a model stack-up left over another table is refused by `model.stackup-copper`. The stack-up merge of "Stack-up across rebuilds" runs on the adapted board, so a stack-up of the script for the new count is written in its place.
- `kicad.layers.added` MUST name the inner layers added.
- `LayerMerge` is a frozen dataclass with `board` (the adapted board design), `added`, `removed` and `issues`. `merge_layers` reports only the codes of the closed table `layers.MERGE_ISSUE_CODES`; they are `kicad.*` codes and pass `PRESERVE_ISSUE_CODES` and `BUILD_ISSUE_CODES` unchanged.

| code | severity | when |
|---|---|---|
| `kicad.layers.removed` | warning | copper on a removed inner layer was dropped (counts per kind) |
| `kicad.layers.stackup-reset` | warning | the board's stack-up did not match the new layers and was removed |
| `kicad.layers.added` | info | inner layers were added for the new copper count |

#### Scenario: Two layers become four
- **GIVEN** a confirmed target-10 blink build whose board was edited by `edit_blink`, after which `design.py` declares `copper=4`
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the board has the copper layers `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu`, the segments and the via of the edit keep their uuids, the pads of `D1` are on the four copper layers, `result.preserved.kept` holds `D1`, `R1` and `U1`, and `issues` holds `kicad.layers.added` naming `In1.Cu` and `In2.Cu`

#### Scenario: Four layers become six
- **GIVEN** a confirmed target-10 build of a blink variant declared with `copper=4`, whose board gets by token edit a segment on `In1.Cu`, after which `design.py` declares `copper=6`
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the board has the copper layers `F.Cu`, `In1.Cu`, `In2.Cu`, `In3.Cu`, `In4.Cu` and `B.Cu`, the segment on `In1.Cu` keeps its uuid and its layer, and `issues` holds one `kicad.layers.added` naming `In3.Cu` and `In4.Cu` and no `kicad.layers.removed`

#### Scenario: Four layers become two
- **GIVEN** a confirmed target-10 build of a blink variant declared with `copper=4`, whose board gets by token edit a segment on `In1.Cu` and a zone on `In2.Cu`, after which `design.py` declares `copper=2`
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the written board names neither `In1.Cu` nor `In2.Cu`, and `issues` holds one `kicad.layers.removed` naming 1 track on `In1.Cu` and one naming 1 zone on `In2.Cu`

#### Scenario: A stale stack-up is removed
- **GIVEN** a confirmed four-layer build whose `setup` gets, by token edit, a stack-up of four copper layers written by KiCad, after which `design.py` declares two copper layers
- **WHEN** the build runs again
- **THEN** the written `setup` holds no `stackup`, and `issues` holds `kicad.layers.stackup-reset`

#### Scenario: A read stack-up goes with the layers it names
- **GIVEN** a four-layer board whose `setup` holds a complete stack-up of four copper layers, which the reader projects into `Board.stackup`, and a `design.py` that declares two copper layers and no stack-up
- **WHEN** the build runs again
- **THEN** files are written, the written board holds no `stackup` and names neither `In1.Cu` nor `In2.Cu`, `Board.stackup` of the built layout is `None`, `summary["stackup"]` is `None`, and `issues` holds `kicad.layers.stackup-reset` and no `model.stackup-copper`

#### Scenario: A table that is not KiCad's
- **GIVEN** a confirmed four-layer build whose copper rows are changed by token edit to `F.Cu`, `In1.Cu`, `In3.Cu` and `B.Cu`
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 5, `issues` holds `layout.copper-mismatch`, and nothing is written

## MODIFIED Requirements

### Requirement: Layer count across rebuilds
`build` over an existing board SHALL keep the layout of a board of every count of `layers.CREATED_COPPER_COUNTS` whose copper layer names equal those of `layers.created_layers(copper)`, SHALL adapt a board whose copper layer names are those of `created_layers` for another count ("Copper layer changes across rebuilds"), and SHALL name the board's copper layers when neither holds.
- The copper rule of "Board content outside the design is kept" MUST hold at 6 and 8 copper layers as at 2 and 4: with equal names the layout is kept, with the board's own layer rows (types and user names set in KiCad) unchanged.
- When the names differ and `layers.created_count(<the board's copper names>)` gives a count, the board MUST be adapted to the script's count by "Copper layer changes across rebuilds", before every other rule, and its layout is kept.
- Otherwise `layout.copper-mismatch` (error, nothing written) MUST name the board's copper layers, their count and the script's count, and its hint MUST name `--discard-layout`, which creates the board on the script's count without its layout, and no `copper=` value.
- A change of the count MUST keep the layout only through "Copper layer changes across rebuilds".

#### Scenario: Six layers rebuilt
- **GIVEN** a confirmed target-10 build of the six-layer blink variant of `design-dsl`, "Copper layer counts in a build"
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, `result.preserved.board` is true, and every file outside `.bak` files has the bytes of the first build

#### Scenario: Layers added in KiCad
- **GIVEN** a confirmed target-10 build of a blink variant declared with `copper=4`, whose board gets the rows `(8 "In3.Cu" signal)` and `(10 "In4.Cu" signal)` right after the `In2.Cu` row by token edit, as KiCad's board setup adds two layers
- **WHEN** `design.py` is changed to `copper=6` and the build runs with `--confirm`
- **THEN** the exit code is 0, `result.preserved.kept` holds `D1`, `R1` and `U1`, and the written board has the six copper layers `F.Cu`, `In1.Cu` to `In4.Cu` and `B.Cu`

#### Scenario: Mismatch names the board's count
- **GIVEN** a confirmed four-layer build whose copper rows are changed by token edit to `F.Cu`, `In1.Cu`, `In3.Cu` and `B.Cu`, a table for which `layers.created_count` gives no count
- **WHEN** `uv run pytest tests/unit/lens/test_preserve_layers.py -k table_that_is_not` builds the unchanged script over it
- **THEN** nothing is written, and `issues` holds one `layout.copper-mismatch` error whose message names the board's copper layers, `In3.Cu` among them, and whose hint names `--discard-layout` and no `copper=` value

#### Scenario: Table that Fenolite does not create
- **GIVEN** a confirmed target-10 build of a blink variant declared with `copper=8`, whose board gets the rows `(16 "In7.Cu" signal)` and `(18 "In8.Cu" signal)` right after the `In6.Cu` row by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 5, `issues` holds one `layout.copper-mismatch` whose message names 10 and 8 and whose hint names `--discard-layout` and no `copper=` value, and nothing is written

### Requirement: Placement precedence
`lens.preserve.effective_placements(placements, match, *, design, board, source={})` SHALL decide each part's placement with the fixed precedence: a locked `place()`, then the existing board, then the part's entry in the placements file (`source`, "Placements file"), then `place()`, then the build's staging (later, c0022's placer). `prepare` SHALL call it, and `cmd_build` SHALL pass the result to `build_design` as its `placements`.
- `placements` MUST be `dsl.placements(design)` (c0011): component path → an object with `at`, `rotation`, `side` and `locked`. "Locked" means `place(…, locked=True)` in the script.
- `source` MUST map component paths to `SourcePlacement` entries. An entry that wins MUST be given as a `KeptPlacement` with the entry's position, rotation, side and lock, so the build writes the entry's lock; that lock gives the entry no precedence.
- For a matched part: a locked `place()` MUST win. Otherwise, when its footprint is off the board, the part's `source` entry MUST win, then its `place()`, and without either the part MUST be left unplaced, so the build stages it again (`layout.unplaced`). Otherwise the footprint's own position, rotation, side and lock MUST be used, as a `KeptPlacement`.
- A footprint is off the board when its position lies outside the closed box `outline.outline_box(design)` (`kicad-file-backend`, "Board outline as rings"), which holds the arcs of the outline as well as its points, and only when the board's edge content is absent or is exactly that outline ("Board content outside the design is kept"). Otherwise no footprint counts as off the board.
- For an unmatched part: a locked `place()`, then its `source` entry, then its `place()`; otherwise it is left unplaced and staged by the build.
- Without an existing board, `prepare` MUST return what `effective_placements` gives with an empty match and `board=None`, which is `placements` unchanged when `source` is empty, and no match. With `board=None` no footprint is off the board, and a design without an outline has none either.
- An unlocked `place()` whose position, rotation or side differs from a kept board placement MUST give `layout.place-overridden` (info), naming the part and both placements, with the hint "lock the placement in the script, move the footprint in KiCad, or re-run with --discard-layout". When it differs from a `source` entry that wins, the same code MUST be given with the hint "lock the placement in the script, or edit placements.toml".
- A `source` entry of a part that keeps a board placement different from the entry MUST give `layout.source-stale` (info) naming the part and both placements, with the hint "run fenolite sync --to-source". An entry that names no part of the design MUST give `layout.source-unknown` (warning).
- A locked `place()` that differs from the board's position, rotation, side or lock MUST give `layout.place-forced` (warning), because the footprint is then re-placed from its definition ("Kept and re-placed footprints").

#### Scenario: The board wins over place()
- **GIVEN** a confirmed target-10 blink build in `B` whose board was edited by `edit_blink`
- **WHEN** the build runs again with `--confirm`
- **THEN** `D1` stays 4 mm right of its `place()` position, `issues` holds one `layout.place-overridden` naming `D1`, and the exit code is 0

#### Scenario: A locked place() wins
- **GIVEN** a confirmed blink build whose `U1`, locked in `design.py`, was moved 2 mm down in its board by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** `U1` is back at its `place()` position and locked, and `issues` holds `layout.place-forced` naming `U1`

#### Scenario: A staged part placed by the script
- **GIVEN** a confirmed build of a blink variant whose `R1` has no `place()`, so it is staged beside the outline, after which `design.py` gains `r1.place(mm(20), mm(10))`
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` is at (120 mm, 110 mm) and `issues` holds no `layout.unplaced`

#### Scenario: A staged part stays staged
- **GIVEN** the same staged build and `design.py` unchanged
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` keeps its staged position, `issues` holds one `layout.unplaced` naming `R1`, and every file keeps its bytes

#### Scenario: The file places an unmatched part
- **GIVEN** an existing blink board without `R1`'s footprint, a design whose `R1` has an unlocked `place()`, and a `source` entry for `R1` at another position
- **WHEN** `effective_placements` runs
- **THEN** `R1` takes the entry's placement as a `KeptPlacement`, and the issues hold one `layout.place-overridden` with the hint that names `placements.toml`

#### Scenario: The board wins over a stale file
- **GIVEN** the board edited by `edit_blink` and a `source` entry for `D1` at its `place()` position
- **WHEN** `effective_placements` runs
- **THEN** `D1` keeps its board placement, and the issues hold one `layout.source-stale` naming `D1`

#### Scenario: A locked footprint in the file
- **GIVEN** no existing board and a `source` entry for `R1` with `locked = true`
- **WHEN** the blink is built
- **THEN** `R1` is written at the entry's position with `(locked yes)`, and a later edit of the board still wins over the entry

#### Scenario: A part on a round board
- **GIVEN** a confirmed build of a blink variant with `board(outline=shape.circle(mm(20), mm(20), mm(40)))` whose `R1` is placed at (20 mm, 5 mm), then rebuilt with `R1`'s `place()` removed
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` keeps its board position, which lies inside `outline_box` though outside the box of the outline's two vertices, and `issues` holds no `layout.unplaced`

### Requirement: Board content outside the design is kept
`lens.preserve.merge_layout` SHALL keep the existing board's layers, graphics, texts, rule areas, title block, paper and every opaque root child (setup, stack-up, groups, dimensions and the rest) unchanged, except the group members that follow a renamed footprint and what "Copper layer changes across rebuilds" and "Outline changes across rebuilds" change, and SHALL keep its edge content in place of the design's outline unless "Outline changes across rebuilds" replaces it. `merge_layout` gains the keyword `lock_outline=False`. The two requirements adapt the existing board first, the layers and then the outline, and every other rule of `merge_layout` applies to the adapted board.
- The layout's `Board` MUST be the adapted existing board with its root slots, so c0017's writer re-emits read content in place.
- Each `members` atom of a root `group` node whose text is a key of the identity map of a footprint kept through an alias ("Kept and re-placed footprints") MUST take the mapped text. No other atom of a group MUST change, and Fenolite MUST NOT add or remove a group.
- When the board holds a `Graphic` on a layer of kind `edge`, every such graphic MUST be kept and the layout's `Board.outline` MUST be `None`. When those graphics are not exactly the edges of the built outline, lines and arcs compared as the edge texts of `outline.edge_texts` (`kicad-file-backend`, "Outline lowering"), `layout.outline-kept` (warning) MUST name both, with the hint "lock the outline in the script with board(..., locked=True), edit it in KiCad, or re-run with --discard-layout". Without edge graphics, the built outline MUST be used.
- The copper layer names of the adapted board, in table order, MUST equal those of `layers.created_layers(copper)`. Otherwise `layout.copper-mismatch` (error) MUST be given, and nothing is written.

#### Scenario: Board setup kept
- **GIVEN** a confirmed blink build whose board's `setup` child has `(pad_to_mask_clearance 0)` changed to `(pad_to_mask_clearance 0.05)` by token edit
- **WHEN** the build runs again
- **THEN** the written `setup` node is tree-equal to the edited one

#### Scenario: Outline edited in KiCad
- **GIVEN** a confirmed blink build whose right `Edge.Cuts` line is moved 5 mm right, with the top and bottom lines lengthened to meet it, by token edit
- **WHEN** the build runs again
- **THEN** the written edge lines equal the edited ones, `issues` holds `layout.outline-kept` whose hint names `locked=True`, and the exit code is 0

#### Scenario: Copper count changed in the script
- **GIVEN** a confirmed two-layer blink build and `design.py` changed to `copper=4`
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 0, the written board has four copper layers, and `issues` holds `kicad.layers.added` and no `layout.copper-mismatch`

#### Scenario: Group follows a renamed footprint
- **GIVEN** a confirmed target-10 blink build whose board gets, by token edit, a root `group` with the uuid `00000000-0000-4000-8000-0000000000f1` holding the footprints of `R1` and `D1`, after which `design.py` renames `R1` to `R7` with `d.moved("R1", "R7")`
- **WHEN** the build runs again
- **THEN** the group holds `footprint_uuid("R7")` and `D1`'s uuid, in the order of the edited group, and keeps its own uuid

#### Scenario: An outline with arcs is kept as written
- **GIVEN** a confirmed build of the rounded board of `design-dsl` "Outline shapes in a build", `design.py` unchanged
- **WHEN** the build runs again
- **THEN** `issues` holds no `layout.outline-kept`, and every file keeps its bytes
