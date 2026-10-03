## ADDED Requirements

### Requirement: No-connect marks in an Altium build
`lens.altium.build_altium` SHALL carry the marks of `Circuit.no_connects` into the schematic as No ERC directives (`altium-schematic-writer`, "No-connect directives on the sheet"), after resolving them with the pins it sets on the components ("Altium build outputs").
- For a component of a KiCad lib id, `lens.altium.kicad_pins` MUST rewrite each mark as it rewrites net members: a pin number stays, a pin name becomes every pin number with that name, and a designator that is neither MUST give `altium.unknown-pin` (error) naming the ref and the designator, with `where` set to the component path.
- For a component of an Altium link, `lens.altium.generic_pins` MUST count a marked designator as a used pin (`altium-schematic-writer`, "Generic component bodies"), so the generic body and the generated library symbol hold it.
- A marked designator MUST pass `ascii.text_problem` like a net member's; otherwise `altium.text-unwritable` (error).
- `Design.validate()` then runs on the model with its pins and rewritten marks, so a pin that is marked and on a net gives `model.no-connect-on-net` (error): the build exits 5 and writes nothing. No `altium.*` code is added.
- `.fenolite/circuit.json` MUST store the rewritten marks, and `summary` MUST also hold `no_connects`, the number of directives written, which `cmd_build` copies into `result`.
- The schematic library symbols of KiCad lib ids, their pin records and pin electrical types, `<name>.PrjPcb`, `<name>.PcbLib` and `<name>.PcbDoc` MUST NOT depend on the marks.
- `docs/altium.md` MUST gain a section on no-connect marks: the DSL call, the directive and its "Suppress All Violations" mode, that a marked pin gets no stub, and that the directive stays at its sheet position when "Tools » Update From Libraries" replaces a body.

#### Scenario: Example builds with three directives
- **WHEN** `fenolite build examples/altium_kicad/no_connect.py --out B --target altium --confirm --json` runs
- **THEN** the exit code is 0, `result.no_connects` is `3`, `result.nets` is `3`, `result.power_ports` is `6`, `result.labels` is `2`, no issue has severity `error`, and `B/.fenolite/circuit.json` holds the marks of `U1` pins `2`, `4` and `8`

#### Scenario: A marked name is rewritten to its number
- **GIVEN** a variant of the example that marks `u1["TP"]` instead of `u1[8]`
- **WHEN** it is built
- **THEN** the schematic bytes equal the example's, and the stored mark is `PinRef(<U1 id>, "8")`

#### Scenario: Marked and connected after resolution
- **GIVEN** a variant of the example with `connect(sig, u1["TP"])` and `no_connect(u1[8])`
- **WHEN** it is built with `--target altium --confirm`
- **THEN** the exit code is 5, `issues` holds `model.no-connect-on-net` whose `where` is `U1-8`, and nothing is written

#### Scenario: Library symbol does not depend on the marks
- **GIVEN** the example and a variant without its `no_connect` call
- **WHEN** both are built
- **THEN** the two `altium_no_connect.SchLib` files and the two `altium_no_connect.PrjPcb` files are equal byte for byte

### Requirement: No-connect sample and author report
`examples/altium_kicad/no_connect.py` (CC0-1.0, authored for Fenolite) SHALL be a design named `altium_no_connect` for the Altium target whose marks can be judged by Altium Designer's compiler, and `docs/evidence/altium-schematic.md` SHALL hold Part N, the protocol of that check.
- The design MUST use the folder's authored `FenoliteDemo.kicad_sym` through its `sym-lib-table`: `J1` (`CONN2`), `R1` (`R_V`) and `U1` (`MCU8`); the nets `VIN` (`J1` 1, `U1` 1 and 6, `R1` 1), `GND` (`J1` 2, `U1` 7) and `OE_N` (`R1` 2, `U1` 5); `Power(VIN, GND)`; `no_connect(u1[2], u1[4], u1[8])`, an input, an output and a passive pin; and `U1` pin `3`, an input, left unconnected and unmarked as the positive control.
- Its built `altium_no_connect.PrjPcb`, `altium_no_connect.SchLib` and binary `altium_no_connect.SchDoc` MUST be committed under `tests/data/altium/no_connect/`, and its ASCII schematic under `tests/data/altium/no_connect/ascii/`, declared in `tests/data/MANIFEST.toml` with `origin = "authored"` together with the script, and compared byte for byte with a fresh build by `tests/unit/lens/test_altium_no_connect_golden.py`. `FENOLITE_GOLDEN_WRITE=1` MUST rewrite them instead.
- Part N MUST name the committed files by their SHA-256 and hold these steps, each with the hypotheses it settles:
  - N1: open the project and the binary schematic in Altium Designer; note any prompt or repair offer, and whether a No ERC directive shows at the ends of `U1` pins `2`, `4` and `8` (`H-A-SCH-NC-RECORD`);
  - N2: compile the project; note every message that names `U1` (`H-A-SCH-NC-ERC`). Expected: none for pins `2`, `4` and `8`, and a floating-input message for pin `3`;
  - N3: repeat N1 and N2 with the ASCII schematic in place of the binary one (`H-A-SCH-NC-RECORD`, `H-A-SCH-NC-ERC`);
  - N4: upload the binary schematic alone to the Altium 365 Viewer; note whether the three directives are drawn (`H-A-SCH-NC-VIEWER`).
- A report follows "Altium author reports": tool as `AD <major>.<minor>` or `A365 Viewer`, the date, one generic outcome per step, no artefact, and only Fenolite's authored files opened or uploaded. A confirmed row gets `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <YYYY-MM-DD>; no artefact)`, or the `A365 Viewer` form for N4.
- `docs/hypotheses.md` MUST register `H-A-SCH-NC-RECORD`, `H-A-SCH-NC-ERC` and `H-A-SCH-NC-VIEWER`, and `docs/evidence/sources.md` MUST register S-0180. `lens.altium.ALTIUM_BUILD_EVIDENCE` MUST name the three hypotheses and MUST stay `INFERRED` after any report ("Altium build evidence").

#### Scenario: Golden files of the example
- **WHEN** `uv run pytest tests/unit/lens/test_altium_no_connect_golden.py` runs
- **THEN** the freshly built files equal the four committed files byte for byte, and Part N names the SHA-256 of each

#### Scenario: Registers hold the new rows
- **WHEN** `grep -cE '^\| H-A-SCH-NC-' docs/hypotheses.md` and `grep -cE '^\| S-0180 ' docs/evidence/sources.md` run
- **THEN** they print `3` and `1`, and `uv run pytest tests/unit/test_hypotheses_register.py tests/unit/test_altium_rows.py` passes

#### Scenario: Envelope evidence
- **WHEN** the example is built with `--target altium --dry-run --json`
- **THEN** `evidence.level` is `INFERRED` and `evidence.hypotheses` contains `H-A-SCH-NC-RECORD`, `H-A-SCH-NC-ERC` and `H-A-SCH-NC-VIEWER`

## MODIFIED Requirements

### Requirement: Altium symbol sources
The Altium build SHALL take each lib id's symbol from one of two sources, chosen by the lib id's form; `lens.altium.symbol_source(lib_id)` returns `altium` or `kicad`.
- A lib id whose library part ends with `.SchLib` in any letter case is an Altium link (`altium`). Its symbol is generic: c0032's body over the union of the designators that the nets or the no-connect marks (`Circuit.no_connects`) name on the components of that lib id (`altium-schematic-writer`, "Generic library symbols"). No library is opened for it.
- Every other lib id is a KiCad lib id (`kicad`). Its symbol MUST be resolved with c0011's `LibraryResolver.symbol` and mapped with `altsym.from_symbol_def`. A lib id that does not resolve MUST raise c0011's `UnresolvedLibrariesError` (`FEN-3001`) with its `kicad.lib.*` issues, which pass through like `model.*` codes, and nothing is written.
- A component of a KiCad lib id MUST get one pin per pin number of body style 1 and the common style, over units 1 … n in order, with the pin's name and electrical type, ids keyed `pin:<path>:<number>`. A net member that names a pin number MUST stay; one that names a pin name MUST be rewritten to every pin number with that name; one that names neither MUST give `altium.unknown-pin`.
- A component of a KiCad lib id without `footprint` MUST take the symbol's `Footprint` property, which then follows c0032's footprint-form check. Footprint libraries are opened only as "Altium footprint sources" says: never for an Altium footprint link, and only through the same resolver for a KiCad one.
- An empty component value MUST take the symbol's `Value` property, as c0011 does.

#### Scenario: Sample reads no library
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder
- **WHEN** the sample is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, every lib id's source is `altium`, and no issue code starts with `kicad.lib.`

#### Scenario: KiCad example resolves from its own table
- **GIVEN** `KICAD_CONFIG_HOME` set to an empty folder
- **WHEN** `fenolite build examples/altium_kicad/design.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, every lib id's source is `kicad`, and the symbols come from `examples/altium_kicad/FenoliteDemo.kicad_sym` through the example's `sym-lib-table`

#### Scenario: Unknown KiCad symbol
- **GIVEN** an example variant with `lib_id="FenoliteDemo:NOPE"`
- **WHEN** it is built with `--target altium --dry-run`
- **THEN** the exit code is 3, stderr carries `FEN-3001`, and nothing is written

#### Scenario: Net member by pin name
- **GIVEN** an example variant that connects `U1["VCC"]`, where `VCC` is the name of pin `8`
- **WHEN** it is built
- **THEN** `.fenolite/circuit.json` names pin `8` in that net, and a member named `XYZ` instead gives `altium.unknown-pin`

#### Scenario: Marked designator in a generic symbol
- **GIVEN** a variant of the sample where `no_connect(u2[5])` marks a designator of `U2` that no net names
- **WHEN** it is built with `--target altium`
- **THEN** the generic symbol of `U2`'s lib id in `FenoliteSample.SchLib` holds the pins `1` to `5`, and `result.no_connects` is `1`
