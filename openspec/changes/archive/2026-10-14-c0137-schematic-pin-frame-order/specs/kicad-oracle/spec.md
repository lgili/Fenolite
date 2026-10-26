## ADDED Requirements

### Requirement: Order of mirror and rotation is asked of the netlist export
`tests/kicad/schematic/test_pin_frame_oracle.py` (marker `needs_kicad`) SHALL settle `H-K-SCH-PINFRAME-ORDER` on 9.0.9 and 10.0.6: on the authored sheet of `tests/_pinframe.py` every pin MUST be on the net of the global label set at its `schlayout.pin_point`, and the control MUST tell the two orders apart. The test is no probe of `PROBES`, and a failure MUST take the four mirrored quarter turns out of `schlayout.PROVED_FRAMES`.

#### Scenario: Twelve frames on the netlist export
- **GIVEN** the sheet of `tests/_pinframe.py` for the running major: the authored symbol `Probe:Frame` with three pins that no rotation or mirror maps onto each other, instances `U1` to `U12` in the frames (0, 90, 180, 270 degrees) × (no mirror, `x`, `y`), one global label per pin at its `pin_point`
- **WHEN** `FENOLITE_REQUIRE=kicad uv run pytest tests/kicad/schematic/test_pin_frame_oracle.py -rA` runs on `kicad-cli` 9.0.9 and on 10.0.6
- **THEN** `kicad-cli sch export netlist` puts each of the 36 pins on the net of its label

#### Scenario: The control
- **GIVEN** the same sheet with each label where the other order (mirror first) puts the pin
- **WHEN** its netlist is exported
- **THEN** the pins of `U6`, `U8`, `U10` and `U12` (90 and 270 degrees with a mirror) are off the nets of their labels and the pins of the other eight instances are on them

#### Scenario: The register follows the runs
- **WHEN** the test has passed on both majors
- **THEN** the row of `H-K-SCH-PINFRAME-ORDER` in `docs/hypotheses.md` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` and names the versions it ran on, and the committed probe files are unchanged

## MODIFIED Requirements

### Requirement: Stacked pins of corpus sheets
`tests/kicad/schematic/test_stacked_corpus.py` (markers `needs_kicad` and `needs_corpus`, major-aware) SHALL ask of sheets Fenolite did not write what "Stacked pins pass ERC, the netlist export and parity" proves on generated sheets: in every demo project of the corpus that the running `kicad-cli` loads, each group of pins of one symbol instance that have one name and connect at one point which nothing else touches (no label, no wire, no pin of another instance) MUST be one net of `kicad-cli sch export netlist` that holds those pins alone, with the name that `netnames.open_name` gives (`H-K-SCH-STACKED-OPEN`).
- **What this covers.** The rule for a stack of same-named pins without a label, and nothing more. No demo sheet is inside the grammar of `sch_netlist.own_netlist` (each holds wires, local labels or sub-sheets), so the whole own netlist of a third-party sheet is NOT compared with KiCad's, and no text MAY say it is.
- **How much.** The demo projects hold few such stacks: on 10.0.6 one project holds 10, all judged with their names, and the other projects are skipped with a reason. The test MUST pin that project and its count (`PINNED`), so that it cannot pass on nothing, and MUST fail when the pinned project gives no stack.
- **Left out.** Hidden power inputs (KiCad joins them by name), instances of derived symbols and of power symbols (their pins are not read here), and a sheet used more than once. The test MUST name each of these in its text. An instance that is mirrored and turned by 90 or 270 degrees takes part like any other: `schlayout.pin_point` turns first and mirrors the turned symbol ("Pin connection points" of `kicad-schematic`).
- The row of `H-K-SCH-STACKED-OPEN` in `docs/hypotheses.md` MUST name the test with the versions it ran on, and MUST NOT name a version it did not run on.

#### Scenario: Stacks of the demo projects
- **WHEN** `FENOLITE_REQUIRE=kicad,corpus uv run pytest tests/kicad/schematic/test_stacked_corpus.py -rs` runs on `kicad-cli` 10.0.6
- **THEN** the project `kicad-demo-10-0-6-sch-017` gives 10 stacks, each one net of KiCad's export with the name `netnames.open_name` gives, and every other project is skipped as holding no such stack or as having no project at the tag
