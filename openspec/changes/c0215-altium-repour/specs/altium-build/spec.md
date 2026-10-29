## MODIFIED Requirements

### Requirement: Copper in an Altium build
The Altium build SHALL write copper and net classes into the planned `<name>.PcbDoc` from exactly one copper source per build, and it SHALL invent no copper: a computed pour is derived from the written document alone ("Pour mode of an Altium build").
- `lens.altium.build_altium(design, …, copper=2, planes=None, copper_source=None, pour="computed")` MUST take the copper layer count of the script (`fenolite.dsl.Design.copper`), its planes ("Internal planes in an Altium build"), at most one `lens.altium.CopperSource(design, origin, where="")`, whose `origin` is `script` or `board`, and the pour mode. `cli/cmd_build.py` MUST pass the count, the planes and the pour mode.
- The sources are: **model**, the tracks, arcs, vias and zones of `design.board` itself (tests, and routers that return model copper, c0016 and c0023); **script**, "Script copper in an Altium build"; **board**, "Copper from a routed KiCad board". A `copper_source` given together with copper in `design.board` MUST raise `ValueError`: one source per build.
- The copper layers MUST be the copper layers of `design.board.layers` when it holds any, else `F.Cu`, `B.Cu` for `copper=2` and `F.Cu`, `In1.Cu`, `In2.Cu`, `B.Cu` for `copper=4`. `lens.altium.pcb_document` MUST pass them as `PcbDocSpec.copper_layers`.
- `pcb_document` MUST pass the source's tracks, arcs, vias and zones to the spec, each net id replaced by its net name, and one `pcbdoc.NetClassSpec` per `design.circuit.netclasses` entry with the names of its nets. Net classes always come from `design`, never from a source.
- The stack values MUST come from `design.board.stackup` when it holds one copper layer per copper layer of the board, in order, with exactly one dielectric between neighbours (for four layers the middle one is the `core`, the outer two are `prepreg`); otherwise from `docboard.StackSpec.default`. A stack-up that is present and does not fit MUST give one `altium.not-lowered` info with `where` = `stackup`.
- Coordinates MUST be read in the frame of the placements, the frame in which the KiCad build writes the same script's board.
- The build's `result` MUST gain `copper`, present whenever the PCB document is planned: an object with `source` (`none`, `model`, `script` or `board`), `from` (the path given to `--copper-from`, else `null`), `layers`, `planes` (an object from layer name to net name), `tracks`, `arcs`, `vias`, `zones`, `net_classes` (counts of what is written) and `placements_from_board` (a count).
- When at least one polygon is written unpoured, the build MUST give one `altium.zones-unpoured` info that names the count and the Altium command "Tools » Polygon Pours » Repour All". When at least one polygon is written poured, it MUST give one `altium.zones-poured` info ("Computed pours are experimental" of `altium-pour`).
- A build of a design without copper, planes and net classes MUST give the PCB document bytes of c0035: the four copper storages stay empty.
- The same copper MUST give the same `<name>.PcbDoc` bytes from each of the three sources, in each pour mode.

#### Scenario: Routed model
- **GIVEN** the routed sample's model: the blink design with `copper=4`, five tracks (two on `F.Cu`, one on each other copper layer), one arc, three through vias, one `GND` zone on `In1.Cu` and `B.Cu`, and the class `PWR`
- **WHEN** `build_altium` runs on it with the pour mode `outline`
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

## ADDED Requirements

### Requirement: Pour mode of an Altium build
`fenolite build --target altium`, `fenolite convert --to altium` and `fenolite panel --target altium` SHALL take `--altium-pour outline|computed` and pass it to `pcbdoc.write_pcbdoc` (`altium-pcb-writer`, "Polygon pour modes"); `lower.write_design`, `AltiumBackend.write` and `lens.altium.build_altium` SHALL take it as `pour=`. The default of the three commands and of those three functions SHALL be `computed` (the maintainer's decision of 2026-10-26, roadmap "Open decisions", row 48); `AltiumBackend.model_roundtrip` SHALL keep `outline`. A change of the default SHALL be a recorded decision of the maintainer.
- `computed` by default without the `geo` extra MUST write every polygon unpoured, as `outline` does, and MUST add one `altium.pour-unavailable` (warning) naming `fenolite[geo]`.
- `result.pcb.pour` MUST hold `mode`, `poured` (a count), `unpoured` (an object from reason to count), `evidence` (the level) and `hypotheses` (the ids the poured polygons used), and MUST be present whenever the PCB document is planned.
- An explicit `--altium-pour computed` without the `geo` extra MUST exit 6 with a hint naming `fenolite[geo]` and write nothing.
- A rewrite of a read document (`rewrite=True`) with `computed` MUST pour every polygon again.
- The page of the agent guide that teaches `build` MUST name `--altium-pour` (`tests/unit/agent/test_pages.py`).

#### Scenario: Computed pour of the routed sample
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pour_build.py -k routed` builds the routed sample with `--altium-pour computed`
- **THEN** `result.pcb.pour.poured` is 2, `result.pcb.pour.unpoured` is empty, the written document holds regions with the indices of both polygons, and no issue is an error

#### Scenario: The default pours
- **WHEN** `fenolite build examples/board_40parts/design.py --target altium --dry-run --json` runs with the `geo` extra (its script declares one `GND` zone on `F.Cu` and `B.Cu`; the kit's `routed` script gets its polygon from `kit_model`, which `build` does not run)
- **THEN** `result.pcb.pour.mode` is `computed` and one `altium.zones-poured` names 2 polygons

#### Scenario: The extra is missing
- **GIVEN** `pyclipper` cannot be imported
- **WHEN** the same build runs with `--altium-pour computed`, and again without the option
- **THEN** the first exits 6 with an error naming `fenolite[geo]` and plans no file; the second exits 0, plans the document with both polygons unpoured, and gives `altium.zones-unpoured` and one `altium.pour-unavailable`
