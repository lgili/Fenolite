## ADDED Requirements

### Requirement: Copper in an Altium build
The Altium build SHALL write copper and net classes into the planned `<name>.PcbDoc` from exactly one copper source per build, and it SHALL invent no copper.
- `lens.altium.build_altium(design, …, copper=2, planes=None, copper_source=None)` MUST take the copper layer count of the script (`fenolite.dsl.Design.copper`), its planes ("Internal planes in an Altium build") and at most one `lens.altium.CopperSource(design, origin, where="")`, whose `origin` is `script` or `board`. `cli/cmd_build.py` MUST pass the count and the planes.
- The sources are: **model**, the tracks, arcs, vias and zones of `design.board` itself (tests, and routers that return model copper, c0016 and c0023); **script**, "Script copper in an Altium build"; **board**, "Copper from a routed KiCad board". A `copper_source` given together with copper in `design.board` MUST raise `ValueError`: one source per build.
- The copper layers MUST be the copper layers of `design.board.layers` when it holds any, else `F.Cu`, `B.Cu` for `copper=2` and `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu` for `copper=4`. `lens.altium.pcb_document` MUST pass them as `PcbDocSpec.copper_layers`.
- `pcb_document` MUST pass the source's tracks, arcs, vias and zones to the spec, each net id replaced by its net name, and one `pcbdoc.NetClassSpec` per `design.circuit.netclasses` entry with the names of its nets. Net classes always come from `design`, never from a source.
- The stack values MUST come from `design.board.stackup` when it holds one copper layer per copper layer of the board, in order, with exactly one dielectric between neighbours (for four layers the middle one is the `core`, the outer two are `prepreg`); otherwise from `docboard.StackSpec.default`. A stack-up that is present and does not fit MUST give one `altium.not-lowered` info with `where` = `stackup`.
- Coordinates MUST be read in the frame of the placements, the frame in which the KiCad build writes the same script's board.
- The build's `result` MUST gain `copper`, present whenever the PCB document is planned: an object with `source` (`none`, `model`, `script` or `board`), `from` (the path given to `--copper-from`, else `null`), `layers`, `planes` (an object from layer name to net name), `tracks`, `arcs`, `vias`, `zones`, `net_classes` (counts of what is written) and `placements_from_board` (a count).
- When at least one polygon is written, the build MUST give one `altium.zones-unpoured` info that names the count and the Altium command "Tools » Polygon Pours » Repour All".
- A build of a design without copper, planes and net classes MUST give the PCB document bytes of c0035: the four copper storages stay empty.
- The same copper MUST give the same `<name>.PcbDoc` bytes from each of the three sources.

#### Scenario: Routed model
- **GIVEN** the routed sample's model: the blink design with `copper=4`, five tracks (two on `F.Cu`, one on each other copper layer), one arc, three through vias, one `GND` zone on `In1.Cu` and `B.Cu`, and the class `PWR`
- **WHEN** `build_altium` runs on it
- **THEN** `routed.PcbDoc` is planned, its summary `copper` holds `"source": "model"`, `"layers": 4`, `"planes": {}`, `"tracks": 5`, `"arcs": 1`, `"vias": 3`, `"zones": 2` and `"net_classes": 1`, `issues` holds one `altium.zones-unpoured` naming 2 polygons, and no issue is an error

#### Scenario: Layer count from the script
- **GIVEN** a blink variant with `design.board(mm(50), mm(30), copper=4)`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `result.copper.layers` is 4, `result.copper.source` is `none` and every other count but `net_classes` is 0

#### Scenario: Design without copper keeps its document
- **GIVEN** a blink variant without its net class
- **WHEN** it is built with `--target altium`
- **THEN** `Vias6`, `Polygons6`, `Classes6` and `Rules6` of its `blink.PcbDoc` have `Header` 0 and an empty `Data`, and every other stream equals the same stream of the committed `tests/data/altium/blink/blink.PcbDoc`

#### Scenario: Two sources refused
- **WHEN** `build_altium` gets the routed model and a `CopperSource` as well
- **THEN** it raises `ValueError` that names both sources

### Requirement: Internal planes in an Altium build
The Altium build SHALL write each inner layer that the script declares as a plane (`design-dsl`, "Board and placements in the DSL") as an internal plane on its net, and every other inner layer as a signal layer (`altium-pcb-writer`, "Four-layer stack"; `H-A-PCB-CU-PLANE`).
- `build_altium(…, planes=…)` MUST take a mapping from layer name to net name, and `cli/cmd_build.py` MUST pass `dsl.planes(design)`. `pcb_document` MUST give the spec the stack of `pcbrecords.copper_stack(layers, planes)` with the plane nets.
- A plane on a layer that is not an inner copper layer of the board, or on a net that the design does not hold, MUST give `altium.copper-stack`.
- The model is not changed: a plane layer is a `copper` layer of the model, and no `LayerKind` is added.
- A zone layer on a plane whose net is the plane's net MUST NOT be written as a polygon: the plane stands for it. The build MUST give one `altium.plane-zone-merged` info that names those zones and layers. The zone's other layers are written as polygons.
- A track or an arc on a plane layer, or a zone layer on a plane with another net or without a net, MUST give `altium.plane-copper` (error): split planes are not written.
- Through vias and pads cross a plane unchanged; no Plane Connect or Plane Clearance rule is written, so Altium's defaults decide how they join it.

#### Scenario: Ground plane from the script
- **GIVEN** the routed sample's script with `design.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})` and the sample's copper
- **WHEN** `build_altium` runs
- **THEN** `result.copper.planes` is `{"In1.Cu": "GND"}`, the document's chain is 1, 39, 3, 32 with `PLANE1NETNAME=GND`, `Polygons6` holds the `B.Cu` polygon only, and `issues` holds one `altium.plane-zone-merged` naming the `GND` zone on `In1.Cu` and one `altium.plane-copper` error for the sample's track on `In1.Cu`

#### Scenario: Plane variant builds
- **GIVEN** the variant `p0` of "Routed sample and author report" (the sample with the plane above and without its track on `In1.Cu`)
- **WHEN** `build_altium` runs
- **THEN** no issue is an error, `result.copper.tracks` is 4 and `result.copper.zones` is 1

#### Scenario: Plane on an unknown net
- **WHEN** `build_altium` runs on the blink with `copper=4` and `planes={"In1.Cu": "NOPE"}`
- **THEN** `files` is empty and `issues` holds one `altium.copper-stack` naming `In1.Cu` and `NOPE`

### Requirement: Script copper in an Altium build
When the design carries resolved script copper, the Altium build SHALL write it. The design carries it as a `CopperSource` with `origin="script"`, whose `design` is the model that the KiCad build of the same script holds in memory after c0028's copper intents are resolved (`lens.build.build_design(…, copper_intents=…).design`): footprints placed, tracks and vias in the frame of the placements, nets of the script.
- This requirement is implemented and tested now. Until c0028 exists, no build of the CLI passes such a source; tests build the KiCad model with `lens.build.build_design` and put the sample's copper into it. c0028 then passes its resolved model, with no change to this requirement.
- The build MUST check a script source as "Copper from a routed KiCad board" checks a board (components, footprints, pad nets, outline, copper nets), so a source built from another script is refused. It MUST take the source's placements and give no `altium.placement-from-board` for this origin.
- The build MUST NOT import `fenolite.dsl` or resolve intents itself: `lens` receives a model (`package-layering`).
- Via types, layers and planes follow "Copper issue codes" and "Internal planes in an Altium build".
- `result.copper.source` MUST be `script`.

#### Scenario: Script source equals the committed sample
- **GIVEN** the KiCad build of the routed sample's script in memory, with the sample's copper put into its model
- **WHEN** `build_altium` runs on the script's model with that design as a `CopperSource` of origin `script`
- **THEN** `result.copper.source` is `script`, no issue is an error, and `routed.PcbDoc` equals the committed `tests/data/altium/routed/routed.PcbDoc` byte for byte

#### Scenario: Source of another script refused
- **GIVEN** the same source, and a script whose `R1` has another footprint
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds one `altium.copper-board-mismatch` whose `where` is `R1`

### Requirement: Copper from a routed KiCad board
`fenolite build DESIGN.py --out DIR --target altium --copper-from BOARD.kicad_pcb` SHALL copy the tracks, arcs, vias and zones of a routed KiCad board of the same design into `<name>.PcbDoc`, after checking that the board matches the design. This requirement extends "Altium build target" and `design-dsl` "Build command".
- `--copper-from` MUST take one path. Without `--target altium` it MUST be a usage error (exit 2, `FEN-2001`); a path that is not a file MUST be a usage error too. `cmd_build` MUST read the board with `fenolite.backends.kicad.pcb.read_board` in the same process: a board the reader refuses exits 3 with the reader's `FEN-3xxx` code, and the reader's warnings and infos pass into `issues` unchanged. `kicad-cli` is not run. `cmd_build` MUST pass `CopperSource(<the read design>, "board", <the path as given>)`, and `--copper-from` wins over any other source.
- **Components.** Each design component with a footprint link MUST match exactly one footprint of the board: by the `fenolite.path` property when the board's footprint holds it, else by reference. A component without a match, a board footprint without a component, or two footprints for one component MUST give `altium.copper-board-mismatch` with `where` = the component path or the board reference.
- **Footprints.** A matched footprint MUST have the component's footprint link as its `lib_ref`, and the same pad numbers at the same positions in the footprint's own frame as the definition written to `<name>.PcbLib`; else `altium.copper-board-mismatch` with `where` = the component path.
- **Placements.** The board's placements win: every matched component MUST be written at the board footprint's position, rotation, side and lock, and none is staged. The copper is only right relative to the footprints as the board places them, and the exported tool project is the source of truth for layout (`design-model`, "Layout authority"). When a placement differs from the script's request, or the script requests none, the build MUST give one `altium.placement-from-board` info that names the refs.
- **Outline.** The bounding box of the board's `Edge.Cuts` graphics (or of its `Board.outline`) MUST equal the bounding box of the design's outline; else `altium.copper-board-mismatch` with `where` = `outline`.
- **Nets.** Every pad of a matched footprint MUST be on the net of the same name as the design puts its pin on, or on none in both; else `altium.copper-board-mismatch` with `where` = `<ref>.<pad number>`. A track, arc, via or zone on a net whose name the design does not hold MUST give one `altium.copper-net-missing` per net name, naming the count of items and the layer and position of the first. Copper without a net is copied without a net.
- **Copper.** Via types, layers and planes follow "Copper issue codes" and "Internal planes in an Altium build"; a zone's `fills` are not copied. Keep-outs, texts, graphics and holes of the board are not copied and give one `altium.not-lowered` info per kind with `where` = the path.
- Every issue of this requirement MUST name the path, and an issue about a copper item MUST name its layer and its position in millimetres from the outline's corner.
- A copper source given while the PCB document is not planned MUST give `altium.copper-no-document` (error).
- `result.copper.source` MUST be `board`, `result.copper.from` the path as given, and `result.copper.placements_from_board` the number of components placed from the board. The result MUST also hold `copper_input`, the board's `path` (as given), `sha256`, the kind `kicad-board` and its `format_version`: the envelope's `input` is one object in contract v0 (`schemas/fenolite.envelope.v0.json`) and stays the script.
- The bytes MUST NOT depend on the ids or uuids of the board's items, on `--seed`, `--timestamp` or `PYTHONHASHSEED`.

#### Scenario: Copper copied from the board
- **GIVEN** `routed.kicad_pcb`, the KiCad build of the routed sample's script with the sample's copper, written by a test helper into a temporary folder beside the script `design.py`
- **WHEN** `fenolite build design.py --out B --target altium --copper-from routed.kicad_pcb --confirm --json` runs
- **THEN** the exit code is 0, `result.copper` holds `"source": "board"`, `"tracks": 5`, `"arcs": 1`, `"vias": 3`, `"zones": 2` and `"placements_from_board": 3`, no `altium.placement-from-board` is given, and `B/routed.PcbDoc` equals the committed `tests/data/altium/routed/routed.PcbDoc` byte for byte

#### Scenario: Moved part follows the board
- **GIVEN** the same board with `R1` moved by 1 mm, together with the track ends on its pads
- **WHEN** the build runs with `--copper-from`
- **THEN** the exit code is 0, `R1`'s component record is at the board's position, and `issues` holds one `altium.placement-from-board` naming `R1`

#### Scenario: Mismatches are located
- **GIVEN** boards derived from `routed.kicad_pcb`: one without `D1`, one whose `R1` has another footprint, one whose `R1` pad `2` is on `GND`, one with a track on a net `EXTRA`, and one with a blind via; and the unchanged board given to a variant of the script with `copper=2`
- **WHEN** each is given to `--copper-from` with `--dry-run --json`
- **THEN** each build exits 5 with no planned file; the first five give one error each, `altium.copper-board-mismatch` with `where` `D1`, `R1` and `R1.2`, `altium.copper-net-missing` naming `EXTRA` and `altium.via-unsupported`; the last gives `altium.copper-layer` errors that name `In1.Cu` and `In2.Cu`; and every message names the board's path

#### Scenario: Option without the Altium target
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --copper-from x.kicad_pcb --dry-run` runs
- **THEN** the exit code is 2, stderr carries `FEN-2001`, and nothing is written

### Requirement: Copper round trip oracle
`tests/kicad/altium/test_copper_from_oracle.py` SHALL prove with `kicad-cli` that copper copied by `--copper-from` survives the way back (S-0161, S-0166, S-0020; `H-A-PCB-CU-ROUNDTRIP`).
- The test MUST write the routed sample's KiCad board (`lens.build.build_design` and the sample's copper) to a temporary folder, build the Altium project from it with `--copper-from`, import the written `routed.PcbDoc` with `kicad-cli pcb import --format altium`, and read both boards with `fenolite.backends.kicad.pcb.read_board`.
- Relative to each board's outline corner and within 10 nm, the imported board MUST hold every track, arc and via of the source board with its layer, net name, geometry, width or sizes, and every zone layer with its net and outline; and it MUST hold no other track, arc, via or zone. Every footprint MUST be at the source's position, rotation and side.
- Zone fills, net classes and uuids are not compared, and the test MUST say why.
- The test MUST be skipped on `kicad-cli` 9.x and required in the `kicad-10` job. A pass on 10.0.6 gives `H-A-PCB-CU-ROUNDTRIP` the level `ORACLE-VERIFIED(kicad-cli)`; it settles no Altium row.

#### Scenario: Board to Altium and back
- **WHEN** `uv run pytest tests/kicad/altium/test_copper_from_oracle.py` runs with `kicad-cli` 10.0.6
- **THEN** the imported board's copper equals the source board's copper item for item, on four copper layers, with no error in the report

### Requirement: Copper issue codes
`lens.altium.ALTIUM_ISSUE_CODES` SHALL gain these rows. This requirement extends c0032's "Altium build issue codes", whose closed-set rule and scenarios hold for them. The lens MUST find each case before `write_pcbdoc` runs, so no `ValueError` of the writer reaches the user. The rows apply to copper of every source.

| code | severity | when |
|---|---|---|
| `altium.copper-stack` | error | the board's copper layers are not `F.Cu`, `B.Cu` or `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu`, their count differs from `copper`, or a plane names a layer that is not an inner layer or a net the design does not hold |
| `altium.copper-layer` | error | a track, arc, via or zone names a layer outside the board's copper layers |
| `altium.via-unsupported` | error | a via is blind, buried or micro, or does not span the top and the bottom layer |
| `altium.zone-unsupported` | error | a zone has fewer than three outline points (an outline kept as an opaque slot) |
| `altium.copper-invalid` | error | a track of zero length, a width of 0 or less, a drill not below its diameter, or a net id that names no net |
| `altium.plane-copper` | error | a track or arc lies on a plane layer, or a zone on a plane layer has another net than the plane |
| `altium.copper-board-mismatch` | error | a copper source does not match the design: a component, a footprint, a pad net or the outline |
| `altium.copper-net-missing` | error | copper of a source is on a net whose name the design does not hold |
| `altium.copper-no-document` | error | a copper source is given and the PCB document is not planned |
| `altium.zones-unpoured` | info | polygons are written without poured copper |
| `altium.plane-zone-merged` | info | a zone on a plane layer with the plane's net is left to the plane |
| `altium.placement-from-board` | info | components are placed as the board of `--copper-from` places them, not as the script requests |

- One issue MUST be given per entity (per net name for `altium.copper-net-missing`), with the entity id, component path or net name in `where` and the layer or via type in the message.
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

#### Scenario: Source without a document
- **GIVEN** a blink variant without `design.board(...)` and a `CopperSource`
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds `altium.copper-no-document`

### Requirement: Copper evidence
`pcbdoc.EVIDENCE` SHALL also name `H-A-PCB-CU-KICAD`, `H-A-PCB-CU-ROUNDTRIP`, `H-A-PCB-CU-TRACK`, `H-A-PCB-CU-VIA`, `H-A-PCB-CU-STACK`, `H-A-PCB-CU-PLANE`, `H-A-PCB-CU-REPOUR`, `H-A-PCB-CU-CLASS`, `H-A-PCB-CU-RULES` and `H-A-PCB-CU-VIEWER`, so `PCB_BUILD_EVIDENCE` and `ALTIUM_BUILD_EVIDENCE` name them under c0035's "PCB evidence and capabilities".
- The levels MUST stay `INFERRED`. `H-A-PCB-CU-KICAD` or `H-A-PCB-CU-ROUNDTRIP` at `ORACLE-VERIFIED(kicad-cli)`, or an author-report row, never raises the build's level.
- With `--copper-from`, the envelope MUST also combine the evidence of the KiCad board reader, lowest wins.
- `docs/hypotheses.md` MUST register the ten rows with backend `altium`, and `tests/unit/test_altium_rows.py` MUST check them.

#### Scenario: Copper rows in the envelope
- **WHEN** the routed model is built
- **THEN** `evidence.level` is `INFERRED` and `evidence.hypotheses` contains `H-A-PCB-CU-REPOUR`, `H-A-PCB-CU-STACK` and `H-A-PCB-CU-PLANE`

#### Scenario: Copper rows registered
- **WHEN** `grep -cE '^\| H-A-PCB-CU-' docs/hypotheses.md` runs
- **THEN** it prints `10`

### Requirement: Routed sample and author report
The routed sample SHALL be committed, checked and handed to the maintainer with a protocol.
- `tests/_altium_copper.py` MUST build the sample's model from data authored for Fenolite: the blink design named `routed` with `copper=4`, plus the copper of "Copper in an Altium build", scenario "Routed model". It MUST also give the same sample as a KiCad-built model and as a written `.kicad_pcb` text, for the script and board sources. No value comes from another project.
- The five files of its Altium build MUST be committed under `tests/data/altium/routed/`, declared in `tests/data/MANIFEST.toml` with `origin = "authored"`, and compared byte for byte with a fresh build by `tests/unit/lens/test_altium_copper_golden.py`; `FENOLITE_GOLDEN_WRITE=1` rewrites them.
- The blink golden files of c0035 MUST be rebuilt once: `blink.PcbDoc` now holds the class `PWR` and its rules. The other four blink files and every file of `tests/data/altium/sample/` MUST keep their bytes.
- With `FENOLITE_ALTIUM_VARIANTS=<folder>`, the golden test MUST also write the bisection variants there, never into the repository: `c0` two layers with tracks and an arc; `c1` adds vias; `c2` the stack of four signal layers with inner tracks; `c3` adds the polygons; `c4` adds the net class; `c5` adds the rules (the committed sample); and `p0`, the sample with `In1.Cu` as a plane on `GND` and without its track on `In1.Cu`.
- `docs/evidence/altium-pcb.md` MUST gain Part C, under the rules of c0035's "PCB author reports":
  - C1 open `routed.PcbDoc` in Altium Designer without a repair prompt; the tracks, the arc and the vias show with their nets, and routed nets show no connection line (`H-A-PCB-CU-TRACK`, `H-A-PCB-CU-VIA`);
  - C2 the Layer Stack Manager lists Top Layer, Mid-Layer 1, Mid-Layer 2 and Bottom Layer as signal layers with three dielectrics (`H-A-PCB-CU-STACK`);
  - C3 the two polygons show as outlines; "Repour All" fills them, and the `GND` pads connect (`H-A-PCB-CU-REPOUR`);
  - C4 the class `PWR` lists `GND` and `VIN`, and the rules editor shows the five rules (`H-A-PCB-CU-CLASS`, `H-A-PCB-CU-RULES`);
  - C5 the Altium 365 Viewer shows the copper on four layers (`H-A-PCB-CU-VIEWER`);
  - C6 open `p0/routed.PcbDoc`: the Layer Stack Manager lists Internal Plane 1 between Top Layer and Mid-Layer 2, the plane is on `GND`, and the `GND` pads and vias that cross it show no connection line (`H-A-PCB-CU-PLANE`).
  - When a step fails, the page tells the maintainer to open `c0` to `c5` in order and report the first that fails.
- Each step MUST name the SHA-256 of its files (for C6 the SHA-256 of `p0/routed.PcbDoc`, which the test rebuilds), and the page MUST list the expected tracks, vias and polygons as (layer, net, geometry in mm).

#### Scenario: Golden routed files
- **WHEN** `uv run pytest tests/unit/lens/test_altium_copper_golden.py tests/unit/lens/test_altium_pcb_golden.py` runs
- **THEN** fresh builds equal the five routed files and the five blink files, and `git diff --exit-code tests/data/altium/sample/` exits 0

#### Scenario: Variants stay outside the repository
- **WHEN** the golden test runs with `FENOLITE_ALTIUM_VARIANTS` set to an empty temporary folder
- **THEN** the folder holds `c0` to `c5` and `p0`, each with a `routed.PcbDoc`, `c5/routed.PcbDoc` equals the committed one, and `git status --short` lists no new file

#### Scenario: Protocol names the routed bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_copper_golden.py -k protocol` reads the page
- **THEN** Part C names the SHA-256 of every committed routed file and of `p0/routed.PcbDoc`, and its copper table equals the sample model's copper

### Requirement: Copper is documented
The copper of the PCB document SHALL be documented as c0035's "PCB writers are documented" requires.
- `docs/formats/altium/pcb-copper.md` MUST hold, in the fact-table form that `tests/unit/test_format_facts.py` checks: the routed track and arc rows, the via record with its offsets, the polygon keys and the unpoured state, the stack keys of a signal mid layer and of an internal plane, the plane net key and what a saved plane holds besides, the class and rule records, the oracle observations, and "Fenolite's choices". A row below `ORACLE-VERIFIED(kicad-cli)` MUST name an `H-A-PCB-CU-*` hypothesis. A row resting on S-0150 MUST name version 1 and its commit. A row that rests on the Altium-saved documents (S-0172, S-0174, S-0175, S-0176, S-0199, S-0200) MUST say that the files stay outside the repository.
- `docs/formats/altium/pcb-document.md` MUST move `Vias6`, `Polygons6`, `Classes6` and `Rules6` out of its list of empty storages and drop "No routing, vias, zones, rules, classes or polygons".
- `docs/altium.md` MUST gain a section "Copper": what is written, the layer table with signal layers and planes, the unpoured polygons and the repour step, the refusals, and the three routes by which copper reaches the document (script copper with c0028, `--copper-from`, and routers with c0016 and c0023), with the checks of `--copper-from` and the rule that the board's placements win. `docs/cli-contract.md` MUST list `--copper-from`, `result.copper` and the twelve codes. `PROVENANCE.md` and `docs/evidence/sources.md` MUST list S-0195 to S-0200.

#### Scenario: Copper fact page checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py tests/unit/test_provenance.py` runs
- **THEN** it checks `pcb-copper.md` and passes

#### Scenario: Copper routes documented
- **WHEN** `docs/altium.md` is read
- **THEN** it names "Repour All", `Mid-Layer 1`, `Internal Plane 1`, `--copper-from`, `altium.via-unsupported`, `altium.copper-board-mismatch` and `altium.zones-unpoured`

## MODIFIED Requirements

### Requirement: PCB document output
The Altium build SHALL plan an experimental `<name>.PcbDoc` from `pcbdoc.write_pcbdoc` when the design has a board outline without cutouts and every component that has a footprint link has a `kicad` link whose footprint is in the planned `<name>.PcbLib`. Otherwise it MUST give one `altium.pcbdoc-not-written` info that names the reason (no board, cutouts, Altium footprint links, or the footprints not written) and the components concerned.
- Components without a footprint link MUST be left off the board, as Altium's change order would leave them.
- A placed component MUST take its DSL placement. An unplaced component MUST be staged right of the outline as the KiCad build stages it (`lens.build.STAGING_OFFSET`, `STAGING_GAP`, top side, angle 0), and the build MUST give one `altium.pcb-staged` info naming the staged refs. With a copper source, a component takes the source's placement instead, and none is staged ("Copper from a routed KiCad board").
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

