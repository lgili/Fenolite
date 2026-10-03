## ADDED Requirements

### Requirement: Copper in an Altium build
The Altium build SHALL write the copper and the net classes that the built model holds into the planned `<name>.PcbDoc`, and it SHALL write nothing else as copper: it has no copper source of its own.
- `lens.altium.build_altium(design, …, copper=2)` MUST take the copper layer count of the script (`fenolite.dsl.Design.copper`, set by `design.board(width, height, copper=…)`), and `cli/cmd_build.py` MUST pass it. No DSL call is added.
- The copper layers MUST be the copper layers of `design.board.layers` when it holds any, else `F.Cu`, `B.Cu` for `copper=2` and `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu` for `copper=4`. `lens.altium.pcb_document` MUST pass them as `PcbDocSpec.copper_layers`.
- `pcb_document` MUST pass `design.board.tracks`, `arcs`, `vias` and `zones` to the spec, each net id replaced by its net name, and one `pcbdoc.NetClassSpec` per `design.circuit.netclasses` entry with the names of its nets.
- The stack values MUST come from `design.board.stackup` when it holds one copper layer per copper layer of the board, in order, with exactly one dielectric between neighbours; otherwise from `docboard.StackSpec.default`. A stack-up that is present and does not fit MUST give one `altium.not-lowered` info with `where` = `stackup`.
- Coordinates MUST be read in the frame of the placements, the frame in which the KiCad build writes the same script's board.
- The build's `result` MUST gain `copper`: an object with `layers`, `tracks`, `arcs`, `vias`, `zones` and `net_classes` (counts of what is written), present whenever the PCB document is planned.
- When at least one polygon is written, the build MUST give one `altium.zones-unpoured` info that names the count and the Altium command "Tools » Polygon Pours » Repour All".
- A build of a design without copper and without net classes MUST give the PCB document bytes of c0035: the four copper storages stay empty.
- Route of the copper, for the record: script copper reaches the model through c0028's intents and router results through c0016 and c0023. Handing them to this build is their work, not this change's.

#### Scenario: Routed model
- **GIVEN** the routed sample's model: the blink design with `copper=4`, five tracks (two on `F.Cu`, one on each other copper layer), one arc, three through vias, one `GND` zone on `In1.Cu` and `B.Cu`, and the class `PWR`
- **WHEN** `build_altium` runs on it
- **THEN** `routed.PcbDoc` is planned, its summary `copper` is `{"layers": 4, "tracks": 5, "arcs": 1, "vias": 3, "zones": 2, "net_classes": 1}`, `issues` holds one `altium.zones-unpoured` naming 2 polygons, and no issue is an error

#### Scenario: Layer count from the script
- **GIVEN** a blink variant with `design.board(mm(50), mm(30), copper=4)`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.copper.layers` is 4 and every other count but `net_classes` is 0

#### Scenario: Design without copper keeps its document
- **GIVEN** a blink variant without its net class
- **WHEN** it is built with `--target altium`
- **THEN** `Vias6`, `Polygons6`, `Classes6` and `Rules6` of its `blink.PcbDoc` have `Header` 0 and an empty `Data`, and every other stream equals the same stream of the committed `tests/data/altium/blink/blink.PcbDoc`

### Requirement: Copper issue codes
`lens.altium.ALTIUM_ISSUE_CODES` SHALL gain these rows. This requirement extends c0032's "Altium build issue codes", whose closed-set rule and scenarios hold for them. The lens MUST find each case before `write_pcbdoc` runs, so no `ValueError` of the writer reaches the user.

| code | severity | when |
|---|---|---|
| `altium.copper-stack` | error | the board's copper layers are not `F.Cu`, `B.Cu` or `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`, or their count differs from `copper` |
| `altium.copper-layer` | error | a track, arc, via or zone names a layer outside the board's copper layers |
| `altium.via-unsupported` | error | a via is blind, buried or micro, or does not span the top and the bottom layer |
| `altium.zone-unsupported` | error | a zone has fewer than three outline points (an outline kept as an opaque slot) |
| `altium.copper-invalid` | error | a track of zero length, a width of 0 or less, a drill not below its diameter, or a net id that names no net |
| `altium.zones-unpoured` | info | polygons are written without poured copper |

- One issue MUST be given per entity, with the entity id in `where` and the layer or via type in the message.
- With an error the build MUST write no file, as c0032 rules. Nothing is dropped to make a document fit.

#### Scenario: Closed set with the copper rows
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k closed_set` runs
- **THEN** every row of this table is produced by at least one test with its severity

#### Scenario: Blind via refused
- **GIVEN** the routed model with one more via of `via_type="blind"` between `F.Cu` and `In1.Cu`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds one `altium.via-unsupported` whose `where` is the via's id

#### Scenario: Copper on a missing layer
- **GIVEN** the routed model built with `copper=2`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds three `altium.copper-layer` errors: the track on `In1.Cu`, the track on `In2.Cu` and the zone

#### Scenario: Three copper layers refused
- **GIVEN** a model whose `board.layers` holds the copper layers `F.Cu`, `In1.Cu` and `B.Cu`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds one `altium.copper-stack` that names the three layers

### Requirement: Copper evidence
`pcbdoc.EVIDENCE` SHALL also name `H-A-PCB-CU-KICAD`, `H-A-PCB-CU-TRACK`, `H-A-PCB-CU-VIA`, `H-A-PCB-CU-STACK`, `H-A-PCB-CU-REPOUR`, `H-A-PCB-CU-CLASS`, `H-A-PCB-CU-RULES` and `H-A-PCB-CU-VIEWER`, so `PCB_BUILD_EVIDENCE` and `ALTIUM_BUILD_EVIDENCE` name them under c0035's "PCB evidence and capabilities".
- The levels MUST stay `INFERRED`. `H-A-PCB-CU-KICAD` at `ORACLE-VERIFIED(kicad-cli)` or an author-report row never raises the build's level.
- `docs/hypotheses.md` MUST register the eight rows with backend `altium`, and `tests/unit/test_altium_rows.py` MUST check them.

#### Scenario: Copper rows in the envelope
- **WHEN** the routed model is built
- **THEN** `evidence.level` is `INFERRED` and `evidence.hypotheses` contains `H-A-PCB-CU-REPOUR` and `H-A-PCB-CU-STACK`

#### Scenario: Copper rows registered
- **WHEN** `grep -cE '^\| H-A-PCB-CU-' docs/hypotheses.md` runs
- **THEN** it prints `8`

### Requirement: Routed sample and author report
The routed sample SHALL be committed, checked and handed to the maintainer with a protocol.
- `tests/_altium_copper.py` MUST build the sample's model from data authored for Fenolite: the blink design named `routed` with `copper=4`, plus the copper of "Copper in an Altium build", scenario "Routed model". No value comes from another project.
- The five files of its Altium build MUST be committed under `tests/data/altium/routed/`, declared in `tests/data/MANIFEST.toml` with `origin = "authored"`, and compared byte for byte with a fresh build by `tests/unit/lens/test_altium_copper_golden.py`; `FENOLITE_GOLDEN_WRITE=1` rewrites them.
- The blink golden files of c0035 MUST be rebuilt once: `blink.PcbDoc` now holds the class `PWR` and its rules. The other four blink files and every file of `tests/data/altium/sample/` MUST keep their bytes.
- With `FENOLITE_ALTIUM_VARIANTS=<folder>`, the golden test MUST also write the bisection variants `c0` to `c5` there, never into the repository: `c0` two layers with tracks and an arc; `c1` adds vias; `c2` the four-layer stack with inner tracks; `c3` adds the polygons; `c4` adds the net class; `c5` adds the rules (the committed sample).
- `docs/evidence/altium-pcb.md` MUST gain Part C, under the rules of c0035's "PCB author reports":
  - C1 open `routed.PcbDoc` in Altium Designer without a repair prompt; the tracks, the arc and the vias show with their nets, and routed nets show no connection line (`H-A-PCB-CU-TRACK`, `H-A-PCB-CU-VIA`);
  - C2 the Layer Stack Manager lists Top Layer, Mid-Layer 1, Mid-Layer 2 and Bottom Layer as signal layers with three dielectrics (`H-A-PCB-CU-STACK`);
  - C3 the two polygons show as outlines; "Repour All" fills them, and the `GND` pads connect (`H-A-PCB-CU-REPOUR`);
  - C4 the class `PWR` lists `GND` and `VIN`, and the rules editor shows the five rules (`H-A-PCB-CU-CLASS`, `H-A-PCB-CU-RULES`);
  - C5 the Altium 365 Viewer shows the copper on four layers (`H-A-PCB-CU-VIEWER`).
  - When a step fails, the page tells the maintainer to open `c0` to `c5` in order and report the first that fails.
- Each step MUST name the SHA-256 of its files, and the page MUST list the expected tracks, vias and polygons as (layer, net, geometry in mm).

#### Scenario: Golden routed files
- **WHEN** `uv run pytest tests/unit/lens/test_altium_copper_golden.py tests/unit/lens/test_altium_pcb_golden.py` runs
- **THEN** fresh builds equal the five routed files and the five blink files, and `git diff --exit-code tests/data/altium/sample/` exits 0

#### Scenario: Variants stay outside the repository
- **WHEN** the golden test runs with `FENOLITE_ALTIUM_VARIANTS` set to an empty temporary folder
- **THEN** the folder holds `c0` to `c5`, each with a `routed.PcbDoc`, `c5/routed.PcbDoc` equals the committed one, and `git status --short` lists no new file

#### Scenario: Protocol names the routed bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_copper_golden.py -k protocol` reads the page
- **THEN** Part C names the SHA-256 of every committed routed file, and its copper table equals the sample model's copper

### Requirement: Copper is documented
The copper of the PCB document SHALL be documented as c0035's "PCB writers are documented" requires.
- `docs/formats/altium/pcb-copper.md` MUST hold, in the fact-table form that `tests/unit/test_format_facts.py` checks: the routed track and arc rows, the via record with its offsets, the polygon keys and the unpoured state, the four-layer stack keys, the class and rule records, the oracle observations, and "Fenolite's choices". A row below `ORACLE-VERIFIED(kicad-cli)` MUST name an `H-A-PCB-CU-*` hypothesis. A row resting on S-0150 MUST name version 1 and its commit. A row that rests on the four Altium-saved documents MUST say that the files stay outside the repository.
- `docs/formats/altium/pcb-document.md` MUST move `Vias6`, `Polygons6`, `Classes6` and `Rules6` out of its list of empty storages and drop "No routing, vias, zones, rules, classes or polygons".
- `docs/altium.md` MUST gain a section "Copper": what is written, the layer table, the unpoured polygons and the repour step, the refusals, and the route by which copper reaches the model (c0028, c0016, c0023). `docs/cli-contract.md` MUST list `result.copper` and the six codes. `PROVENANCE.md` and `docs/evidence/sources.md` MUST list S-0195 to S-0198.

#### Scenario: Copper fact page checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it checks `pcb-copper.md` and passes

#### Scenario: Repour step documented
- **WHEN** `docs/altium.md` is read
- **THEN** it names "Repour All", `Mid-Layer 1`, `altium.via-unsupported` and `altium.zones-unpoured`

## MODIFIED Requirements

### Requirement: PCB document output
The Altium build SHALL plan an experimental `<name>.PcbDoc` from `pcbdoc.write_pcbdoc` when the design has a board outline without cutouts and every component that has a footprint link has a `kicad` link whose footprint is in the planned `<name>.PcbLib`. Otherwise it MUST give one `altium.pcbdoc-not-written` info that names the reason (no board, cutouts, Altium footprint links, or the footprints not written) and the components concerned.
- Components without a footprint link MUST be left off the board, as Altium's change order would leave them.
- A placed component MUST take its DSL placement. An unplaced component MUST be staged right of the outline as the KiCad build stages it (`lens.build.STAGING_OFFSET`, `STAGING_GAP`, top side, angle 0), and the build MUST give one `altium.pcb-staged` info naming the staged refs.
- When the PCB document is planned, the board, the placements and the net classes MUST NOT be reported by `altium.not-lowered`: the document holds them ("Copper in an Altium build"). Differential pairs still are, and so are a board's keep-outs, texts, graphics and holes, one issue per kind; these kinds extend the list of c0032's `altium.not-lowered` row.
- The planned write MUST have the kind `altium_pcbdoc`, and the project file MUST list it as `[Document2]`.
- The document MUST follow c0032's edited-output rule: a document changed in Altium is refused with `FEN-7001`, and `--discard-layout` replaces it with a `.bak`. Fenolite never merges an edited document.

#### Scenario: Document of the KiCad-footprint sample
- **WHEN** `examples/blink_2layer/design.py` is built with `--target altium --confirm --json` into an empty folder `B`
- **THEN** the exit code is 0, `B/blink.PcbDoc` is written with the kind `altium_pcbdoc`, `result.pcb_document` is `B/blink.PcbDoc`, `B/blink.PrjPcb` lists it as `[Document2]`, and `issues` holds no `altium.not-lowered` and no `altium.pcb-staged`

#### Scenario: No board, no document
- **GIVEN** a blink variant without `design.board(...)`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `B/blink.PcbLib` is planned, no `.PcbDoc` is planned, and `issues` holds `altium.pcbdoc-not-written` naming the missing board

#### Scenario: Unplaced part is staged
- **GIVEN** a blink variant whose `R1` is not placed
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** `B/blink.PcbDoc` is planned, `issues` holds `altium.pcb-staged` naming `R1`, and `R1`'s component record has the position the KiCad build of the same variant stages it at, converted as `altium-pcb-writer` "PCB document placement" says

