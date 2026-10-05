## ADDED Requirements

### Requirement: Hierarchical sheets in a build
`fenolite build` SHALL write every child sheet that `generate_schematic` returns, as "Built project files" allows for added keyword arguments and steps of `build_design`, and as "Build command" allows for added options.
- **Option.** `--schematic-layout readable|grid` (default `readable`) MUST be passed to `build_design` as the keyword-only argument `schematic_layout`, and from there to `generate_schematic` as `layout`; any other value of the argument MUST raise `ValueError`. With `--schematic skip` the option has no effect; with `--target altium` it MUST be a usage error (exit 2, `FEN-2001`).
- **Files.** After `<name>.kicad_sch`, `build_design` MUST add one file per entry of `generated.children`, at its path under the output folder, from `sch.write_schematic(child, target=target, allow_lossy=allow_lossy)`. `.fenolite/build.json` MUST record the SHA-256 of each.
- **Replaced sheet.** A child file whose bytes are neither the planned bytes nor those whose SHA-256 the last build record holds MUST give `build.schematic-replaced`, as the root does; the build MUST NOT read it.
- **Stale sheet.** A `.kicad_sch` file under `sheets/` that the last build record lists and this build does not plan MUST give `build.sheet-stale` (warning) naming it, and MUST be left in place: the build deletes nothing.
- **Result.** `result.schematic` MUST also hold `sheets` (the number of sheets, root included), `wires` and `satellites` (the number of snapped satellites).
- **Stand-in update.** `tests/_layout_edit.py::update_from_schematic(board_text, schematic_texts)` MUST take the root and child texts keyed by path. For a footprint whose symbol is in a child sheet, `sheetname` MUST be the `Sheetname` of the reference to that sheet and `sheetfile` the `Sheetfile` text that names its file: the values that `kicad-cli`'s netlist export lists as the component's `Sheetname` and `Sheetfile` properties on both majors. Footprints of root symbols keep the form of "Boards updated from the schematic keep their layout".
- The codes `build.sheet-file-collision` and `build.sheet-stale` join the build's closed set ("Build issue codes").

#### Scenario: Module sheets written
- **GIVEN** the lens acceptance design of c0069 (`tests/data/lens/acceptance/design.py`)
- **WHEN** it is built for target 10 with `--confirm --json`
- **THEN** `receipt.written` lists `<name>.kicad_sch`, `sheets/io.kicad_sch` and `sheets/power.kicad_sch`, `result.schematic.sheets` is 3, and a second build writes every file with the same bytes

#### Scenario: Grid layout on request
- **WHEN** the same design is built with `--schematic-layout grid`
- **THEN** `receipt.written` holds no file under `sheets/`, the schematic holds no wire, and `result.schematic.satellites` is 0

#### Scenario: Module removed later
- **GIVEN** a confirmed build of that design, after which the module `io` is removed from `design.py`
- **WHEN** the build runs again with `--confirm`
- **THEN** `issues` hold one `build.sheet-stale` naming `sheets/io.kicad_sch`, the file is still there, and the root no longer names it

#### Scenario: Board survives the first readable build
- **GIVEN** a confirmed v0.2a-form build of that design, made with `--schematic-layout grid`, whose board was then edited by moving two footprints by token edit
- **WHEN** it is built again with the default layout
- **THEN** the two footprints keep their edited positions, every footprint `path` takes the hierarchical form, and `issues` hold no `layout.orphan` and no `layout.net-removed`

## MODIFIED Requirements

### Requirement: Board follows the schematic
`lens.build.lower_for_schematic(design, generated) -> Design` SHALL return the design that `write_triad` writes when a schematic is written, so that KiCad's parity test and its update find the board in agreement with the sheet.
- **Unconnected pads.** Each pad named by `generated.pad_nets` MUST get a net of that name, with the id `derived_id("net", "fenolite", "unconnected:<component path>:<pad number>")`, no net class and no member. Every other pad and net MUST be unchanged.
- **Symbol paths.** `Component.path` of each component named by `generated.paths` MUST be `/<kicad uuid of its instance with the lowest unit>` for a symbol of the root sheet, and `/<kicad uuids of the sheet references from the top down>/<kicad uuid of that instance>` for a symbol of a child sheet (`H-K-SCH-HIER-PATH`), which the board writer emits as the footprint's `path`.
- **Stored layout.** `BuildOutput.layout`, the `.fenolite/` texts and `BuildOutput.design` MUST NOT hold those nets: their pads of unconnected pins stay on no net, and `Design.validate()` reports nothing about them.
- **Net names.** Created nets are written in KiCad's stored form by the board writer (`kicad-file-backend`, "Net names in KiCad's stored form"), and labels carry the same form.
- The function MUST be pure, and applying it twice MUST give the result of applying it once.

#### Scenario: Pads of unconnected pins
- **WHEN** the blink is built for target 10 and the board text is parsed
- **THEN** pad `2` of `U1` holds `(net "unconnected-(U1-PA1-Pad2)")`, pad `16` holds `(net "unconnected-(U1-Pad16)")`, and the footprint of `U1` holds a `path` child whose text is `/` followed by the uuid of the symbol `U1` in `blink.kicad_sch`

#### Scenario: Numbered form for target 9
- **WHEN** the blink is built for target 9
- **THEN** the net table of the board holds 29 rows whose names start with `unconnected-(U1-`, each referenced by exactly one pad

#### Scenario: Stored model stays clean
- **WHEN** `.fenolite/circuit.json` and `.fenolite/board.json` of that build are loaded
- **THEN** no net name starts with `unconnected-`, pad `2` of `U1` has no net, and `fenolite check B --stages model.validate --json` reports no `model.single-pin-net` that names an `unconnected-` net

#### Scenario: Slash net
- **GIVEN** a blink variant whose net `LED_A` is named `mod/LED_A`
- **WHEN** it is built for target 10
- **THEN** the pads and the labels hold `mod{slash}LED_A`, `.fenolite/circuit.json` holds `mod/LED_A`, and a second build is byte-identical

#### Scenario: Path of a symbol in a child sheet
- **GIVEN** the design of "Two modules, one nested" built for target 10
- **WHEN** the board text is parsed
- **THEN** the footprint of `C1` holds a `path` child whose text is `/`, the uuid of the sheet reference `power`, `/`, the uuid of the sheet reference `ldo`, `/` and the uuid of the symbol `C1`

### Requirement: Schematic netlist guard in a build
A build that writes a schematic SHALL prove, before it returns any file and without any tool, that the sheet it generated means the circuit, as a step that "Built project files" allows after `schgen.generate_schematic`.
- The guard MUST compute `sch_netlist.own_netlist(generated.sheet, project=name, children=generated.children)` and compare it with the expected netlist of the design: each net of the circuit under `netnames.stored_name` of its name, with each member named by its component's reference and its pad number (the pin number mapped through `pin_pad_map`), and each entry of `generated.pad_nets` as a net of one node under its name. A pin on no net whose name is not in `pad_nets` MUST only be required to be a net of one node.
- A net or a node on one side only, or a grammar issue, MUST give one `build.schematic-netlist-differs` issue of severity `error`, naming the first net and `REF-PIN` in sorted order, and the build MUST return no file (exit 5).
- The code SHALL join the closed build issue set of "Build issue codes".
- With `schematic="skip"` the guard MUST NOT run.
- The guard MUST NOT compare `pintype`, net classes or component values: it is about connectivity.

#### Scenario: Examples pass the guard
- **WHEN** `uv run pytest tests/unit/lens/test_build_netlist_guard.py -k examples` builds the blink and the units design for targets 9 and 10
- **THEN** no `build.schematic-netlist-differs` is reported, and `files` holds the schematic

#### Scenario: Generator defect caught
- **GIVEN** a `generate_schematic` patched in the test to put the label of `R1` pin `2` on pin `1`
- **WHEN** `build_design` runs for the blink
- **THEN** `files` is empty, and `issues` holds one `build.schematic-netlist-differs` error naming `LED_A` or `LED_DRV` and `R1-1` or `R1-2`

#### Scenario: Skipped schematic, no guard
- **WHEN** the blink is built with `schematic="skip"` and the same patch
- **THEN** the build returns its files and no `build.schematic-netlist-differs`

#### Scenario: Hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** the blink is built with a schematic
- **THEN** the build succeeds

#### Scenario: Module sheets pass the guard
- **WHEN** `uv run pytest tests/unit/lens/test_build_netlist_guard.py -k modules` builds the design of "Two modules, one nested" for targets 9 and 10
- **THEN** no `build.schematic-netlist-differs` is reported, and `files` holds the root and three child sheets
