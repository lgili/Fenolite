## MODIFIED Requirements

### Requirement: Copper from a routed KiCad board
`fenolite build DESIGN.py --out DIR --target altium --copper-from BOARD.kicad_pcb` SHALL copy the tracks, arcs, vias and zones of a routed KiCad board of the same design into `<name>.PcbDoc`, after checking that the board matches the design. This requirement extends "Altium build target" and `design-dsl` "Build command".
- `--copper-from` MUST take one path. Without `--target altium` it MUST be a usage error (exit 2, `FEN-2001`); a path that is not a file MUST be a usage error too. `cmd_build` MUST read the board with `fenolite.backends.kicad.pcb.read_board` in the same process: a board the reader refuses exits 3 with the reader's `FEN-3xxx` code, and the reader's warnings and infos pass into `issues` unchanged. `kicad-cli` is not run. `cmd_build` MUST pass `CopperSource(<the read design>, "board", <the path as given>)`, and `--copper-from` wins over any other source.
- **Components.** Each design component with a footprint link MUST match exactly one footprint of the board: by the `fenolite.path` property when the board's footprint holds it, else by reference. A component without a match, a board footprint without a component, or two footprints for one component MUST give `altium.copper-board-mismatch` with `where` = the component path or the board reference.
- **Footprints.** A matched footprint MUST have the component's footprint link as its `lib_ref`, and the same pad numbers at the same positions in the footprint's own frame as the definition written to `<name>.PcbLib`; else `altium.copper-board-mismatch` with `where` = the component path.
- **Placements.** The board's placements win: every matched component MUST be written at the board footprint's position, rotation, side and lock, and none is staged. The copper is only right relative to the footprints as the board places them, and the exported tool project is the source of truth for layout (`design-model`, "Layout authority"). When a placement differs from the script's request, or the script requests none, the build MUST give one `altium.placement-from-board` info that names the refs.
- **Outline.** The bounding box of the board's `Edge.Cuts` graphics (or of its `Board.outline`) MUST equal the bounding box of the design's outline; else `altium.copper-board-mismatch` with `where` = `outline`.
- **Nets.** Every pad of a matched footprint MUST be on the net of the same name as the design puts its pin on, or on none in both; else `altium.copper-board-mismatch` with `where` = `<ref>.<pad number>`. A net of the board whose name starts with `unconnected-(` and that holds one pad counts as no net: a board built beside a schematic names the pad of each unconnected pin as KiCad does (`design-dsl`, "Board follows the schematic"). A track, arc, via or zone on a net whose name the design does not hold MUST give one `altium.copper-net-missing` per net name, naming the count of items and the layer and position of the first. Copper without a net is copied without a net.
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

#### Scenario: Board built beside a schematic
- **GIVEN** the blink built for KiCad with its schematic, so the pads of its 29 unconnected pins are on `unconnected-(…)` nets
- **WHEN** `fenolite build examples/blink_2layer/design.py --out A --target altium --copper-from <that board> --dry-run --json` runs
- **THEN** the exit code is 0 and `issues` holds no `altium.copper-board-mismatch`
