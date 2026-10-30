## ADDED Requirements

### Requirement: Block layout files
A block layout SHALL be a TOML file with `schema` `fenolite.block-layout.v0`, `block`, `block_version`, `parts_digest`, `nets_digest`, `licence`, `evidence`, a `parts.<local path>` table per part (`at`, `rotation`, `side`, `footprint`) and `tracks`, `arcs`, `vias` and `zones` by local net (`port:<PORT>`, `port:<PORT>.<member>`, `net:<name>`). Lengths and angles MUST be text with a unit, exact; another key MUST be `FEN-3004`.

#### Scenario: A layout is read exactly
- **GIVEN** the authored layout `tests/data/blocks/lib/layouts/divider.toml`
- **WHEN** `uv run pytest tests/unit/reuse/test_blocklayout.py -k read` reads it
- **THEN** `top` is at `(0, 0)` and `bot` at `(0, 2500000)` nm, turned by `90000000` µdeg, the track is on `port:OUT` with width `250000` nm, and no float was created

#### Scenario: Unknown key and inexact length
- **WHEN** a copy with a key `colour` and a copy with `at = ["0.0000001mm", "0mm"]` are read
- **THEN** each raises `FEN-3004` naming the file, the first naming `colour`

### Requirement: Block layout digests
`parts_digest` SHALL be `sha256:` and the SHA-256 of the canonical JSON of the list, sorted by local path, of each part's local path, footprint lib id and sorted pad numbers. `nets_digest` SHALL be the same over the sorted triples of local path, pad number and local net, with `nc` for no net and `global:<name>` for a script-named net that no port binds. Both MUST be computed after part selection.

#### Scenario: A value change keeps the digests, a case change does not
- **GIVEN** the authored divider block built with its default values, with another resistor value, and with the project default `resistor={"case": "0402"}`
- **WHEN** `uv run pytest tests/unit/reuse/test_blocklayout.py -k digests` computes the three digests
- **THEN** the first two give equal `parts_digest` and `nets_digest`, and the third a different `parts_digest`

### Requirement: Block layouts applied
A `.toml` path given to `b.layout(reuse=...)` or `inst.layout(reuse=...)` SHALL be read as a block layout at level 5 of the placement precedence: each child that no level 1 to 4 source places MUST be placed at its layout position composed with the block pose, exactly, with no search. `result.placement.blocks` MUST give the layout's path, SHA-256 and status.

#### Scenario: A divider placed from its layout
- **GIVEN** `examples/blocks/layouts.py`, where `sense_a` uses the authored layout and `sense_a.place(mm(10), mm(8))`
- **WHEN** `uv run pytest tests/unit/cli/test_build_block_layout.py -k placed` builds it
- **THEN** `sense_a/top` is at 10 mm, 8 mm, `sense_a/bot` at 10 mm, 10.5 mm, both turned by 90°, and the layout status is `applied`

#### Scenario: A placement edit wins over the layout
- **GIVEN** the same design with `edits.toml` moving `sense_a/bot` (c0250), or with `sense_a/bot` locked by `place()`
- **WHEN** the build runs
- **THEN** `sense_a/bot` is where the edit or the locked `place()` puts it, and `sense_a/top` is at its layout position

### Requirement: Block layout copper
With `copper=True` and an equal `nets_digest`, each item SHALL be mapped by the block pose, its local net remapped to the parent net joined to that port or to `<instance>/<name>`, and its layers mapped through the stack, mirrored for a bottom pose; an end that leaves its listed pad MUST drop the item as `pad-lost`. The copies MUST then be settled as c0210 specifies and kept as locked items.

#### Scenario: Copper follows the ports
- **GIVEN** the design of "A divider placed from its layout" with `copper=True` and `sense_a.OUT` joined to `ADC0`
- **WHEN** `uv run pytest tests/unit/cli/test_build_block_layout.py -k copper` builds it
- **THEN** the copied `port:OUT` track is on `ADC0` between `sense_a/top` pad 2 and `sense_a/bot` pad 1, it is locked, and the copper check finds nothing new

### Requirement: Block layouts refused on mismatch
A layout whose `block` differs from the instance's block id, or whose major version differs, SHALL give `reuse.layout-block` (error) and nothing written. A different `parts_digest` MUST give `reuse.layout-stale` (warning) naming both digests and the first difference, and the layout MUST NOT be applied. A different `nets_digest` MUST place the parts, copy no copper and give `reuse.layout-nets` (warning).

#### Scenario: A changed part set is never laid out wrongly
- **GIVEN** the authored divider with the project default `resistor={"case": "0402"}` and its 0603 layout
- **WHEN** `uv run pytest tests/unit/cli/test_build_block_layout.py -k stale` builds it with `--confirm`
- **THEN** the exit code is 0, `issues` hold one `reuse.layout-stale` naming `sense_a` and the footprint `Fenolite:Chip_0402`, both parts are staged, and no copper of the layout is written

#### Scenario: A layout of another block
- **WHEN** the divider instance is given a layout whose `block` is `Test:rc_filter`
- **THEN** the exit code is 5, `issues` hold `reuse.layout-block`, and nothing is written

### Requirement: Older and changed layouts
A layout with equal digests and an older minor or patch `block_version` SHALL be applied with `reuse.layout-older` (info). When the file's SHA-256 differs from the one `.fenolite/build.json` recorded and items kept from the board do not follow it, the build MUST give `reuse.layout-changed` (info) naming the instance.

#### Scenario: A layout of version 1.0.0 on block 1.1.0
- **GIVEN** the authored block at version `1.1.0` with equal digests and its layout of `1.0.0`
- **WHEN** `uv run pytest tests/unit/cli/test_build_block_layout.py -k older` builds it
- **THEN** the layout is applied and `issues` hold one `reuse.layout-older` naming both versions

### Requirement: Layout in the block record
`fenolite blocks show` SHALL give `layout`: the path that the block body's `b.layout(reuse=...)` names when the block runs with its defaults, or `null` when it names none.

#### Scenario: A block with a layout
- **WHEN** `uv run pytest tests/unit/cli/test_build_block_layout.py -k record` runs `fenolite blocks show Test:divider --json`
- **THEN** `layout` is `layouts/divider.toml`

### Requirement: Block layout capture
`fenolite blocks capture BOARD --instance PATH` SHALL write a block layout of a laid-out block instance under the plan and confirm protocol: positions through the inverse of the instance's pose (`--origin pose`) or relative to its anchor part (`--origin anchor`), and copper chosen by c0227's group rule. Copper joining a pad outside the instance MUST stay out with `blocks.capture-copper-left` (info) naming the net.

#### Scenario: Capture from a bench board
- **GIVEN** the build of `tests/data/blocks/bench/divider.py`, laid out by hand with one `port:OUT` track and a ground via
- **WHEN** `uv run pytest tests/unit/cli/test_blocks_capture.py -k bench` runs `fenolite blocks capture OUT --instance dut -o divider.toml --dry-run`, then `--confirm --plan`
- **THEN** the written file equals `tests/data/blocks/lib/layouts/divider.toml`, the receipt holds its SHA-256, and two captures give equal bytes

#### Scenario: Port copper that leaves the block
- **GIVEN** a board where the `OUT` track continues to the pad of `U1`, outside the instance
- **WHEN** the capture runs
- **THEN** the track is not in the file, and `issues` hold one `blocks.capture-copper-left` naming the net of `OUT`

### Requirement: Capture round trip
Before writing, `capture` SHALL apply the captured layout in memory to the instance through the same frame and fit the board's instance onto it with c0210's `fit_block` at a tolerance of 1 µm. A part without a fit or a copied item dropped by the settling MUST give `blocks.capture-check-failed` (error), and nothing is written. A part of the instance not on the board MUST give `blocks.capture-unplaced` (error).

#### Scenario: A part missing from the board
- **WHEN** `uv run pytest tests/unit/cli/test_blocks_capture.py -k unplaced` captures an instance whose `bot` was never placed
- **THEN** the exit code is 5, `issues` hold `blocks.capture-unplaced` naming `dut/bot`, and no plan is made

### Requirement: Block layout codes
`reuse.layout-block` (error), `reuse.layout-stale`, `reuse.layout-nets` (warning), `reuse.layout-older`, `reuse.layout-changed` (info) SHALL join `fenolite.reuse.codes.ISSUE_CODES`; `blocks.capture-unplaced`, `blocks.capture-check-failed` (error), `blocks.capture-escape` (warning) and `blocks.capture-copper-left` (info) SHALL join the block codes. Each MUST be explained by `fenolite explain` and listed in `docs/cli-contract.md`, "Block layouts".

#### Scenario: Every block layout code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** each of the nine codes has an entry, the `reuse.*` codes with the heading `build` and the `blocks.*` codes with the heading `blocks`

### Requirement: Laid-out boards verified by KiCad
A built board whose block instances use block layouts, on the top and on the bottom, SHALL read back through `kicad-cli` with every footprint at its resolved placement, and KiCad DRC MUST report no violation and no unconnected item between the pads of an instance whose copper was copied.

#### Scenario: Both sides in KiCad
- **WHEN** `uv run pytest tests/kicad/blocks/test_block_layouts.py` builds `examples/blocks/layouts.py` with one instance on each side for targets 9 and 10
- **THEN** each footprint lies at its recorded placement, and `kicad-cli pcb drc` reports neither a violation nor an unconnected item inside either instance
