## ADDED Requirements

### Requirement: Mask and paste of imported pads
A pad read from an Altium document SHALL be given mask and paste layers by its kind when it is converted to KiCad: a surface pad its side's paste and mask layers, a plated or unplated through-hole pad both mask layers and no paste.
- A manual expansion MUST become the pad's margin; a rule expansion the margin of the first enabled rule of scope `All`.
- A pad that a rule of another scope may govern MUST be a `pad-margin` loss; a rule selecting no pad (`IsVia`) is left out.

#### Scenario: Openings after conversion
- **GIVEN** an imported design with a surface pad of manual mask expansion 2 mil, a plated through-hole pad and an unplated hole, all with the paste mode of a rule
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py` prepares it for KiCad
- **THEN** the surface pad holds `F.Cu`, `F.Paste` and `F.Mask` with a mask margin of 50 800 nm, the two holes hold both masks and no paste, and the written board loads in `kicad-cli`

#### Scenario: A scoped rule is reported
- **GIVEN** the same design whose document holds a `SolderMaskExpansion` rule of scope `All` and one of scope `IsPad` that comes first
- **WHEN** it is prepared
- **THEN** the rule-mode pads take the `All` rule's expansion and the ledger lists them under `pad-margin`

#### Scenario: A rule of vias is no pad's
- **GIVEN** the same design whose `SolderMaskExpansion` rule of scope `IsVia` comes before the one of scope `All`
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py -k no_pad` prepares it
- **THEN** the pads take the `All` rule's expansion and the ledger lists no `pad-margin` row

### Requirement: Pad margins in the KiCad writers
`Pad.mask_margin` and `Pad.paste_margin` SHALL be optional lengths that the KiCad board and footprint writers write as `solder_mask_margin` and `solder_paste_margin` for a pad that holds no such child; the readers SHALL project the first such child into the field and keep the child as read.
- A field that disagrees with a kept child MUST be refused with `projection-read-only`.

#### Scenario: A margin written and a kept one guarded
- **GIVEN** an authored footprint whose pad sets `mask_margin` to 0.1 mm, and a read footprint whose pad holds `(solder_mask_margin 0.05)`
- **WHEN** `uv run pytest tests/unit/convert/test_pad_layers.py -k writer` writes both, the second with `mask_margin` set to 0.1 mm
- **THEN** the first holds `(solder_mask_margin 0.1)` and the second is refused

### Requirement: Model placement of imported footprints
`FootprintDef.placements` SHALL hold, for a footprint read from another format, each 3D model's path, offset, rotation and scale, and the KiCad footprint writer SHALL write one `model` child per placement.
- An embedded Altium model of a top-side part MUST be extracted beside the derived library and placed as in the source; a model of a bottom-side part or turned about X or Y MUST be a loss of kind `model`.

#### Scenario: A rotated body
- **GIVEN** an imported top-side footprint whose body names an embedded model turned by 90° about Z and raised by 0.5 mm
- **WHEN** `uv run pytest tests/unit/convert/test_model_placement.py` converts it to KiCad
- **THEN** the library footprint names the extracted `.step` with `(offset (xyz 0 0 0.5))` and `(rotate (xyz 0 0 -90))`, and the file holds the model's bytes

#### Scenario: A model on the bottom
- **GIVEN** the same footprint placed on the bottom side
- **WHEN** it is converted
- **THEN** no model is written and the report lists one `model` loss with the reason

### Requirement: Library made from a board
`fenolite library BOARD --out LIB [--diff LIBRARY]` SHALL write each footprint of a KiCad board, brought back to its origin, rotation 0 and the top side, into the footprint library `LIB` (a `.pretty` folder), under the mutation protocol.
- Instances of one name that differ MUST be written as `<name>_2` and so on, with `library.instances-differ` (warning).
- `--diff` MUST report per footprint the kinds that differ and write nothing.

#### Scenario: Silkscreen edited on the board
- **GIVEN** an authored board whose instances of `R_0603` have their silkscreen clipped, and a library with the unclipped footprint
- **WHEN** `fenolite library <board> --diff old.pretty --json` runs
- **THEN** the reply names `R_0603` with the kind `silkscreen`, the exit code is 5, and nothing is written

#### Scenario: Two instances that differ
- **GIVEN** an authored board with two `R_0603` instances, one with a pad moved
- **WHEN** `fenolite library <board> --out lib.pretty --dry-run --json` runs
- **THEN** the plan writes `R_0603.kicad_mod` and `R_0603_2.kicad_mod`, and the issues hold one `library.instances-differ`

### Requirement: Library command result
The result of `fenolite library` (schema `fenolite.library.v0`) SHALL hold `board`, `library` and either `footprints` (one row per written footprint: `name`, `source` and `refs`) or, with `--diff`, `drift` (one row per footprint: `name` and `kinds`); that list is paged with `--limit`.

#### Scenario: Paged rows
- **GIVEN** the example board of the command
- **WHEN** `uv run pytest tests/unit/cli/test_paging.py` lists the paged commands
- **THEN** `library` pages `drift|footprints`
