## ADDED Requirements

### Requirement: No-connect marks in the DSL
`fenolite.dsl.part.no_connect(*pins) -> None` SHALL mark each pin handle as intentionally unconnected, and `fenolite.dsl` SHALL re-export `no_connect` (an addition under "DSL package": `part.py` imports nothing new).
- Each argument MUST be a pin handle such as `u1[11]` or `u1["TP"]`; any other value MUST raise `DslError`. A call without arguments does nothing. Pins of several parts MAY be marked in one call.
- The designator MUST be stored as written in `Part.no_connects`, a set of `str`, and resolved only by the build ("No-connect marks in a build"). `u1[11]` and `u1["11"]` name the same mark, and marking a designator twice keeps one mark.
- `no_connect` on a designator that `connect` joined to a net MUST raise `DslError` naming the ref, the designator and the net. `connect` on a marked designator MUST raise `DslError` naming the ref and the designator. In both cases the earlier call stays in force.
- A mark belongs to its part: it joins the design when the part is added, before or after the call, and a part that is never added carries no mark into the model.
- `to_model` MUST set `Circuit.no_connects` to one `PinRef(<component id>, <designator as written>)` per mark, in `PinRef` order (`design-model`, "No-connect marks in the circuit model"), and MUST change nothing else: `Component.pins` stays empty and no net is created.
- There is no `Part` method for marks, no automatic marking of unused pins and no way to remove a mark.
- `docs/dsl.md` MUST gain a section "No-connect marks" with the call, the errors, the stored form and what each target does with a mark.

#### Scenario: Marks in the model
- **GIVEN** `u1 = Part("U1", "Mini:Mini_QFP32_IC")` added to a design, and `no_connect(u1[12], u1[11], u1["11"])`
- **WHEN** `to_model(design)` runs
- **THEN** `circuit.no_connects` is `(PinRef(<U1 id>, "11"), PinRef(<U1 id>, "12"))`, `U1` has `pins == ()`, and the circuit holds no net

#### Scenario: Marking a connected designator
- **WHEN** `connect(en, u1[11])` is followed by `no_connect(u1[11])`
- **THEN** `DslError` is raised naming `U1`, `11` and `EN`, and `to_model` gives no mark

#### Scenario: Connecting a marked designator
- **WHEN** `no_connect(u1[11])` is followed by `connect(en, u1[11])`
- **THEN** `DslError` is raised naming `U1` and `11`, and the net `EN` gets no member

#### Scenario: Not a pin handle
- **WHEN** `no_connect("U1.11")` or `no_connect(u1)` is called
- **THEN** `DslError` is raised

#### Scenario: Re-export and import rule
- **WHEN** `python -c "from fenolite.dsl import no_connect; print(no_connect.__module__)"` and `uv run pytest tests/unit/test_import_graph.py` run
- **THEN** the first prints `fenolite.dsl.part`, and the second passes with no `ALLOWED` change

### Requirement: No-connect marks in a build
The KiCad build (`lens.build.build_design`) SHALL resolve every mark of `Circuit.no_connects` to pin numbers by the rules of "Pins and pads in a build", refuse a pin that is marked and connected, and keep the marks in the `.fenolite/` model. It writes no schematic, so no written KiCad file changes.
- A designator MUST be read as a pin number first, and otherwise as a pin name that marks every pin with that name. A designator that is neither MUST give `build.unknown-pin` (error) naming the ref and the designator. A number that is also another pin's name MUST give `build.pin-ambiguous` (warning), and the number wins.
- After resolution, a pin that is marked and that a net lists MUST give `build.no-connect-on-net` (error) naming the ref, the pin number and the net; the build MUST exit 5 and write nothing. This code joins the `build` envelope under "Build issue codes": it MUST be a key of `lens.build.BUILD_ISSUE_CODES` with severity `error`, and `docs/cli-contract.md` MUST list it.
- After the build, `Circuit.no_connects` MUST hold `PinRef(<component id>, <pin number>)` in `PinRef` order without duplicates, and `.fenolite/circuit.json` MUST store them.
- `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`, the library tables and the vendored files MUST be byte for byte those of the same design without marks: the pad of a marked pin gets no net, as the pad of any unconnected pin, and `build.unused-pin-without-pad` applies to a marked pin as to any unconnected pin.
- A rebuild takes the marks from the script; the layout lens neither reads nor keeps a mark from the board.
- The KiCad schematic writer of v0.2a lowers these marks to KiCad's no-connect flags; until then the marks serve `fenolite check` ("ERC lite stage" of `verification-loop`).

#### Scenario: Marks resolved in the built model
- **GIVEN** a blink variant with `u1 = Part("U1", "Mini:Mini_QFP32_IC", ...)`, its `GND` pins connected, and `no_connect(u1[11], u1[12])`
- **WHEN** it is built with `--confirm` into `B` and `B/.fenolite` is loaded with `canonical.load_dir`
- **THEN** the exit code is 0 and `circuit.no_connects` is `(PinRef(<U1 id>, "11"), PinRef(<U1 id>, "12"))`

#### Scenario: Written KiCad files do not change
- **GIVEN** the variant above and the same variant without the `no_connect` call
- **WHEN** both are built with the same `--seed` and `--timestamp`
- **THEN** every planned file outside `.fenolite/` has the same SHA-256 in both receipts

#### Scenario: A name and a number of one pin
- **GIVEN** `connect(gnd, u1["GND"])` and `no_connect(u1[10])` on `Mini:Mini_QFP32_IC`, whose pin `10` is named `GND`
- **WHEN** the design is built with `--confirm`
- **THEN** the exit code is 5, `issues` holds `build.no-connect-on-net` naming `U1`, `10` and `GND`, and nothing is written

#### Scenario: Unknown marked designator
- **GIVEN** `no_connect(r1["X"])` on `Mini:Mini_R`
- **WHEN** the design is built with `--confirm`
- **THEN** the exit code is 5 and `issues` holds `build.unknown-pin` naming `R1` and `X`

#### Scenario: New code in the closed set
- **WHEN** `uv run pytest tests/unit/lens/test_build_issues.py -k closed_set` and `uv run pytest tests/consistency` run
- **THEN** both pass, `BUILD_ISSUE_CODES["build.no-connect-on-net"]` is `error`, and a build test produces the code
