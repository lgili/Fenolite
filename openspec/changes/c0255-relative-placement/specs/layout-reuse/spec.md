## ADDED Requirements

### Requirement: Block layout reuse in a build
A block reuse SHALL place each child that no level 1 to 4 source places from the reference board's part with the same block-local path, at its position in the reference board's `place()` frame composed with the block pose. c0210's per-part fit MUST run under that transform only, giving `reuse.no-fit` for pads that differ; a child without a reference part MUST be staged with `reuse.unknown-part` (warning).

#### Scenario: A block placed from its own board
- **GIVEN** `blocks/buck.kicad_pcb`, an authored layout of the block alone, and `p3.layout(reuse="blocks/buck.kicad_pcb")` with `p3.place(mm(20), mm(5))`
- **WHEN** `uv run pytest tests/unit/cli/test_build_reuse.py -k placed` builds the design
- **THEN** every pad of `buck3`'s parts lies within 1 µm of its reference pad moved by 20 mm and 5 mm

### Requirement: Nets mapped by port
With `copper=True`, each reference net SHALL map to the parent net joined to the instance's port of that name, or to the instance's local net of that name; the tracks, arcs, vias and zones of the block MUST then be copied and settled as c0210 and c0227 specify, with this map and no inference, and kept as locked items. A reference net that is neither a port nor a local net MUST give `reuse.port-unmapped` (error).

#### Scenario: Copper follows the ports
- **GIVEN** the same reference board, whose `VIN` and `GND` are ports and `FB` a local net, and `p3`'s `VIN` joined to `V12`
- **WHEN** `uv run pytest tests/unit/cli/test_build_reuse.py -k copper` builds with `copper=True`
- **THEN** the copied `VIN` copper is on `V12`, the `FB` copper on `buck3/FB`, every copy is locked, and the copper guard finds nothing new

#### Scenario: A net without a port
- **GIVEN** a reference board with a net `TEST` that the block neither exports nor declares
- **WHEN** the build runs with `copper=True` and `--confirm`
- **THEN** the exit code is 5, `issues` hold `reuse.port-unmapped` naming `TEST`, and nothing is written

### Requirement: Block reuse codes
`reuse.port-unmapped` (error) SHALL join `fenolite.reuse.codes.ISSUE_CODES`, explained by `fenolite explain` and listed in `docs/cli-contract.md`, "Layout reuse".

#### Scenario: The code is explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs
- **THEN** `reuse.port-unmapped` has an entry whose `see` is the heading `build`
