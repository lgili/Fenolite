## ADDED Requirements

### Requirement: Pads command
`fenolite pads PATH [REF [NUMBER]] [--origin X,Y]` SHALL be registered by `src/fenolite/cli/cmd_pads.py` with `mutates=False`, and SHALL list the pads of a board in the board frame from the board model, without running any tool. It is the query a script author needs to route by hand: where a pad is, on which layers and on which net.
- `PATH` MUST resolve with `projectset.resolve_board`; the board is read through `registry.for_path`, narrowed to `BoardFrame` for the pads (`backend-protocol`, "Board-frame protocol").
- `result.pads` MUST hold one object per `BoardPad`, in board order and pad order: `where` (`REF-NUMBER`), `ref`, `number`, `index`, `kind`, `position`, `rotation`, `side`, `layers`, `net`, `box` and `drill`.
  - `index` MUST be the position of the pad among the pads of its footprint that carry the same number, from 0: the value that `Part.pad(number, index=…)` takes (`design-dsl`, "Copper intents in the DSL").
  - `position` is `[x, y]`, `box` is `[x0, y0, x1, y1]`, the bounding box of the pad's copper over its copper layers, or `null` for a pad without copper. `net` is the net's name or `null`, `drill` the drill size or `null`.
  - Lengths MUST be integer nanometres and the rotation integer microdegrees.
- With `REF`, only the pads of that footprint MUST be listed, matched as `find_pads` matches: by component path first, else by reference. With `NUMBER`, only the pads that carry that number. `result.count` MUST be the number of listed pads.
- `--origin` MUST be two lengths with units, parsed with `core.units.parse_length`, default `0mm,0mm`. Every `position` and `box` MUST be reported relative to it, and `result.origin` MUST hold it. `docs/dsl.md` MUST tell a script author to pass the DSL's board origin, so that the numbers are the ones `Design.track` takes.
- An unknown reference MUST exit 2 with `FEN-2001` and the closest references in the hint; a number that the footprint does not have MUST exit 2 with the footprint's pad numbers in the hint; an origin without units MUST exit 2.
- The output MUST be deterministic and hold no absolute path.
- **Evidence.** `Evidence.combine` of the board read's evidence and `frame.EVIDENCE`.
- `example_args` MUST be `(EXAMPLE_BOARD, "R1")`.
- `docs/cli-contract.md` MUST describe the command and its result keys.

#### Scenario: Pads of one part
- **WHEN** `uv run fenolite pads tests/data/kicad/board/two_layer.kicad_pcb R1 --json` runs
- **THEN** the exit code is 0, `result.count` is 2, and `result.pads` holds `R1-1` on net `VCC` at `[20000000, 15800000]` and `R1-2` on net `LED_A` at `[20000000, 14200000]`, both with `kind` `smd`, `side` `top`, `index` 0, `drill` `null` and a `box` that contains their position

#### Scenario: One pad of a through-hole part
- **WHEN** `uv run fenolite pads tests/data/kicad/board/two_layer.kicad_pcb D1 1 --json` runs
- **THEN** `result.count` is 1, the pad is `D1-1` on net `GND` with `kind` `thru_hole`, `side` `bottom`, `layers` naming `F.Cu` and `B.Cu`, and `drill` 800000

#### Scenario: Positions relative to an origin
- **WHEN** the first command runs with `--origin 10mm,10mm`
- **THEN** `result.origin` is `[10000000, 10000000]`, and the position of `R1-1` is `[10000000, 5800000]`

#### Scenario: Whole board
- **WHEN** `uv run fenolite pads tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.count` is 4, in the order `R1-1`, `R1-2`, `D1-1`, `D1-2`

#### Scenario: Unknown reference and unknown number
- **WHEN** `fenolite pads <board> R9` and `fenolite pads <board> R1 7` run
- **THEN** both exit 2 with `FEN-2001`; the first hint names `R1`, and the second names the pad numbers `1` and `2`

#### Scenario: The command is hermetic and read-only
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py tests/unit/cli/test_check_readonly.py` run `pads` with its `example_args`
- **THEN** it exits 0, and the SHA-256 of every file of the board's folder is unchanged
