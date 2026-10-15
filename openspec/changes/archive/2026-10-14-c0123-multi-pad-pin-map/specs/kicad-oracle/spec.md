## ADDED Requirements

### Requirement: Stacked pins pass ERC, the netlist export and parity
`tests/kicad/schematic/test_generated_oracle.py` and `tests/kicad/schematic/test_own_netlist.py` (marker `needs_kicad`, major-aware) SHALL prove on 9.0.9 and 10.0.6 that a project `build` writes for a design with pins of several pads is read by KiCad as the circuit says. The design is the stacked design of `tests/_schbuild.py`, authored from the `Mini` library: passive pins with two pads on nets, an `output` pin with two pads on a net, two `power_in` pins with two pads on nets, a marked pin with three pads whose numbers sort before and after the pin's, a named pin with two pads on no net without a mark whose first pad is not the lowest, and a part with a map of one pad per pin.
- **Netlist** (`H-K-SCH-STACKED`, `H-K-SCH-STACKED-OPEN`). The nets of `kicad-cli sch export netlist` MUST equal those of `sch_netlist.own_netlist` of the same sheets: the same nodes on nets of the same names, the nets of open pins included.
- **ERC.** `sch erc --format json --severity-all` MUST report, for this design, exactly the violations it reports for the same design built with the first pad of each pin only: stacking adds none.
- **Parity.** `pcb drc --schematic-parity` on the built board MUST report no parity entry, and `fenolite check` on the project MUST report no `parity.*` finding and no `parity.oracle-differs`.
- **Re-save.** `sch upgrade --force` of the generated sheet MUST keep the stacked pins and the nets.
- The outcomes MUST be recorded as the other outcomes of the generated schematic are (`docs/evidence/kicad/probes/<version>.json`), and `docs/formats/kicad/schematic.md` MUST hold one row for each of the two hypotheses with its measured versions.

#### Scenario: Both majors
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/schematic/test_generated_oracle.py tests/kicad/schematic/test_own_netlist.py -k stacked` runs on `kicad-cli` 10.0.6 and, in the pinned image, on 9.0.9
- **THEN** every test passes on both, and the two rows of `docs/hypotheses.md` name both versions

#### Scenario: Name of an open stack
- **GIVEN** the marked, unnamed pin of `U1` with the pads `5`, `15` and `9`, and the pin `K` of `D2` with the pads `21` and `17`, on no net and without a mark
- **WHEN** the netlist is exported
- **THEN** it holds one net `unconnected-(U1-Pad15)` with three nodes and one net `Net-(D2-K-Pad17)` with two

### Requirement: Stacked pins of corpus sheets
`tests/kicad/schematic/test_stacked_corpus.py` (markers `needs_kicad` and `needs_corpus`, major-aware) SHALL ask of sheets Fenolite did not write what "Stacked pins pass ERC, the netlist export and parity" proves on generated sheets: in every demo project of the corpus that the running `kicad-cli` loads, each group of pins of one symbol instance that have one name and connect at one point which nothing else touches (no label, no wire, no pin of another instance) MUST be one net of `kicad-cli sch export netlist` that holds those pins alone, with the name that `netnames.open_name` gives (`H-K-SCH-STACKED-OPEN`).
- **What this covers.** The rule for a stack of same-named pins without a label, and nothing more. No demo sheet is inside the grammar of `sch_netlist.own_netlist` (each holds wires, local labels or sub-sheets), so the whole own netlist of a third-party sheet is NOT compared with KiCad's, and no text MAY say it is.
- **How much.** The demo projects hold few such stacks: on 10.0.6 one project holds 10, all judged with their names, and the other projects are skipped with a reason. The test MUST pin that project and its count (`PINNED`), so that it cannot pass on nothing, and MUST fail when the pinned project gives no stack.
- **Left out.** Hidden power inputs (KiCad joins them by name), instances of derived symbols and of power symbols (their pins are not read here), a sheet used more than once, and an instance that is mirrored and turned by 90 or 270 degrees: for such an instance two demo sheets connect the pins where "rotate, then mirror" puts them and `schlayout.pin_point` mirrors first, which is reported apart from this change (change c0137). The test MUST name each of these in its text.
- The row of `H-K-SCH-STACKED-OPEN` in `docs/hypotheses.md` MUST name the test with the versions it ran on, and MUST NOT name a version it did not run on.

#### Scenario: Stacks of the demo projects
- **WHEN** `FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/schematic/test_stacked_corpus.py -rs` runs on `kicad-cli` 10.0.6
- **THEN** the project `kicad-demo-10-0-6-sch-017` gives 10 stacks, each one net of KiCad's export with the name `netnames.open_name` gives, and every other project is skipped as holding no such stack or as having no project at the tag
