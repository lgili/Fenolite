## ADDED Requirements

### Requirement: Boards updated from the schematic keep their layout
A rebuild over a board that KiCad updated from the generated schematic SHALL keep the layout, as it does for any other edit of the board. Because no headless command runs KiCad's "Update PCB from Schematic", the proof uses a stand-in, and what the real update writes stays a hypothesis (`H-K-SCH-UPDATE`).
- `tests/_layout_edit.py::update_from_schematic(board_text, schematic_text) -> str` MUST return the board with, for each footprint whose reference a symbol of the schematic has: `(sheetname "/")` and `(sheetfile "<name>.kicad_sch")` added, the footprint's `path` set to `/<symbol uuid>`, and each footprint property that the symbol also has rewritten with the symbol's text. It MUST change nothing else.
- On a board written by a build with a schematic, the stand-in MUST change no `path` and no property text: the build already wrote what the update would write (`design-dsl`, "Board follows the schematic").
- A rebuild over the stand-in's output MUST match every footprint ("Footprint matching"), keep every position, rotation, side and lock, keep every track and via, and give no `layout.orphan`, no `layout.footprint-replaced` and no `layout.net-removed`.
- The `sheetname` and `sheetfile` children MUST survive the rebuild as opaque slots of their footprints.
- The `fenolite.path` property of a footprint MUST still be the secondary key after the stand-in, because the symbol carries the same property ("Footprint matching").

#### Scenario: Stand-in is a no-op on paths and fields
- **GIVEN** a confirmed target-10 blink build with a schematic
- **WHEN** `uv run pytest tests/unit/lens/test_build_schematic.py -k stand_in` applies `update_from_schematic` to its board
- **THEN** the result differs from the built board only by the added `sheetname` and `sheetfile` children

#### Scenario: Rebuild after the stand-in
- **GIVEN** the same build, routed by `tests/_layout_edit.py::edit_blink` and then passed through the stand-in
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `result.preserved.kept` lists `D1`, `R1` and `U1`, the tracks and the via of the edit are present with their uuids, the footprints still hold `sheetname` and `sheetfile`, and `issues` holds no `layout.orphan`, `layout.footprint-replaced` or `layout.net-removed`

#### Scenario: Both majors accept the result
- **WHEN** `uv run pytest tests/kicad/lens/test_update_stand_in.py -rA` runs on 9.0.9 and on 10.0.6
- **THEN** `kicad-cli` loads the rebuilt board, and its parity test reports nothing
