## ADDED Requirements

### Requirement: An argument's name is its flag
Each option's `name` SHALL be its first long flag without the leading dashes in the description of a
command (`fenolite capabilities --command NAME`, `fenolite.cli.describe`), and a new field `dest` SHALL hold
the parser's destination. A positional's `name` stays its destination (change c0495).

#### Scenario: The power paths of analyze
- **WHEN** `fenolite capabilities --command analyze --json` runs
- **THEN** the argument with flag `--path` has `name` `path` and `dest` `power_paths`

#### Scenario: Every command
- **WHEN** `uv run pytest tests/unit/cli/test_describe.py -k flag_names` describes every command
- **THEN** for every option, `"--" + name` is one of its flags

## MODIFIED Requirements

### Requirement: Net command
`fenolite net PATH [NAME]` SHALL be registered by `src/fenolite/cli/cmd_net.py` with `mutates=False` and `paged = "nets|net.pads"`, and SHALL describe the nets of a board, or one net, from the board model, without running any tool.
- `PATH` MUST resolve with `projectset.resolve_board` when it is a `.kicad_pcb`, a `.kicad_pro` or a folder, else through `registry.for_path`; the board is read through `registry.for_path`, narrowed to `BoardFrame` for the pads, so an Altium `.PcbDoc` is read (change c0495). A file no `BoardFrame` backend reads MUST exit 2 with `FEN-2001` naming the file without its folder and listing the suffixes that are read.
- **Without `NAME`.** `result.nets` MUST be `analysis.views.net_list(design)`: one row per net, sorted by name, with `name`, `class`, `pads`, `tracks`, `vias`, `zones` and `length` (the summed centre-line length of its tracks and arcs, in nm).
- **With `NAME`.** `result.net` MUST be `analysis.views.net_view(design, NAME, pads=…)`: `name`, `class`, `pads` (each `where` as `REF-PIN`, `layers`, `position`), `copper` (per layer: `tracks`, `arcs`, `length`), `vias`, `zones` (each `layers` and `filled`) and `box` (the bounding box of its pads and copper, or `null`). The paged list is then `net.pads`.
- An unknown name MUST exit 2 with `FEN-2001` and the three closest net names in the hint.
- Lengths MUST be integer nanometres. The output MUST be deterministic and hold no absolute path.
- **Evidence.** `Evidence.combine` of the board read's evidence and `frame.EVIDENCE`.
- `example_args` MUST be `(EXAMPLE_BOARD,)`.

#### Scenario: Net list of the authored board
- **WHEN** `uv run fenolite net tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** `result.nets` names `GND`, `LED_A` and `VCC` in this order, each with its pad and track counts

#### Scenario: One net
- **WHEN** `fenolite net tests/data/kicad/board/two_layer.kicad_pcb GND --json` runs
- **THEN** `result.net.pads` lists the pads of `GND` as `REF-PIN`, and `result.net.copper` gives a length in nm per layer that has tracks

#### Scenario: Unknown net
- **WHEN** `fenolite net tests/data/kicad/board/two_layer.kicad_pcb GDN` runs
- **THEN** the exit code is 2 and the hint names `GND`

#### Scenario: An Altium PCB document
- **WHEN** `fenolite net tests/data/slots/slots_altium.PcbDoc --json` runs
- **THEN** the exit code is 0, `result.nets` lists the document's nets, and `input.kind` is `pcbdoc`
