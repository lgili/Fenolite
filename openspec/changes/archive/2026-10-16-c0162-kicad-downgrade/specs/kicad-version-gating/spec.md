## ADDED Requirements

### Requirement: Downgrade resolver
`src/fenolite/backends/kicad/data/downgrade.toml` SHALL hold one row per token row of `tokens.toml` whose `since_major` is above a target of `TARGET_MAJORS`, per such form row, and per key path of `pro.TEN_ONLY_PATHS`. A row MUST name its `id`, its `target` and an `action` among `rewrite`, `same`, `presentation` and `design`, and MAY name the values `when` with an action `else` for the other values; a `rewrite` row MUST hold its `form` and its sources.

#### Scenario: Each row proved on 9.0.9
- **WHEN** `uv run pytest tests/kicad/downgrade/test_rows.py -rA` runs in the pinned 9.0.9 and 10.0.6 images
- **THEN** each row's bench gives `equal` (load, DRC or ERC by type, and the upgrade at level 5 for `rewrite` and `same` rows), and a row whose bench differs has the action `design`

### Requirement: Downgrade resolver closure
`resolver.load()` SHALL check the table against `tokens.toml` and `pro.TEN_ONLY_PATHS` and MUST fail, naming the row, on a missing row, an unknown id, a repeated id or an incomplete `rewrite`.

#### Scenario: Table is closed
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_downgrade_resolver.py -k closed` loads the table
- **THEN** every row of `tokens.toml` with `since_major` 10 and every path of `TEN_ONLY_PATHS` has exactly one resolver row, and removing one makes `load()` fail naming it

### Requirement: Downgrade edits
`resolver.resolve(root, kind, target)` SHALL edit, for each `kicad.token.too-new` issue of `check_emittable(root, kind, target)`, the node that the issue locates, inside opaque content too: a `rewrite` row replaces it by its `form`, and `same`, `presentation` and `design` rows remove it. It MUST NOT remove a node that holds the construct, and `check_emittable` on the returned tree MUST report no error.

#### Scenario: Setup kept
- **GIVEN** the KiCad 10.0.6 demo board `CM5_MINIMA_3` in the corpus
- **WHEN** it is written with `write_board(design, target=9, downgrade=True, allow_lossy=True)`
- **THEN** the written board holds its `setup` node with its `tenting` in 9's form `(tenting front back)`, the 633 `tenting` nodes of its pads, whose sides are all `none`, are removed as `same`, and the counts per row equal those of the design's measurement

### Requirement: Downgrade consent
`resolver.resolve` SHALL return the tree, the row of each edit and the counts per row and action. A `design` edit MUST raise `LossyWriteError` naming its row unless the writer was given `allow_lossy`; with it the node is removed and the row reported as a loss. A `project:` row MUST be `same` when its key holds what a fresh KiCad 10 project writes there, and `design` otherwise.

#### Scenario: Design loss needs consent
- **GIVEN** a board of major 10 with one via whose `capping` is set
- **WHEN** `write_board(design, target=9, downgrade=True)` runs, and again with `allow_lossy=True`
- **THEN** the first raises `LossyWriteError` naming the row `capping`, and the second writes the board without the node and reports the row

#### Scenario: Default project sections
- **GIVEN** a KiCad 10 project whose `component_class_settings`, `tuning_profiles` and class `tuning_profile` hold what a fresh KiCad 10.0.6 project writes, and the same project with a tuning profile
- **WHEN** each is written with `update_project(text, design, target=9, downgrade=True)` for a board read at 10
- **THEN** the first drops the three sections as `same` without `allow_lossy`, and the second raises `LossyWriteError` naming the row `project:/tuning_profiles`

## MODIFIED Requirements

### Requirement: Targets and downgrade refusal
`check_target(info, target_major, *, downgrade=False)` SHALL return `FORMAT_VERSIONS[info.kind][target_major]` when `target_major` is in `TARGET_MAJORS`, the input is `SUPPORTED`, and the target is not older than `major_for(info.kind, info.version)` or `downgrade` is true. With `downgrade` true the caller MUST resolve the tree with `resolver.resolve` before the emit check ("Downgrade resolver"). It MUST raise:
- `ValueError` for a target outside `TARGET_MAJORS`;
- `UnsupportedFormatError` (`FEN-3003`) when the input is `TOO_OLD`;
- `FutureFormatError` (`FEN-3002`) when the input is `FUTURE`;
- `DowngradeRefusedError` (`cli_code` `FEN-7002`, carrying `source_major`, `target_major` and a `hint` naming the lowest allowed target and `fenolite convert <project> --to kicad --kicad-version <target>`) when the target is older than the input's major and `downgrade` is false.

#### Scenario: Same-major target
- **GIVEN** a board read at `20241229`
- **WHEN** `check_target(info, 9)` is called
- **THEN** it returns `20241229`

#### Scenario: Upgrade target allowed
- **GIVEN** a board read at `20241229`
- **WHEN** `check_target(info, 10)` is called
- **THEN** it returns `20260206`

#### Scenario: Downgrade refused
- **GIVEN** a board read at `20250513` (major 10)
- **WHEN** `check_target(info, 9)` is called
- **THEN** `DowngradeRefusedError` is raised with `source_major == 10`, `target_major == 9` and `cli_code == "FEN-7002"`

#### Scenario: Downgrade on request
- **GIVEN** a board read at `20250513` (major 10)
- **WHEN** `check_target(info, 9, downgrade=True)` is called
- **THEN** it returns `20241229`

#### Scenario: Too-old input refused
- **GIVEN** a board read at `20221018`
- **WHEN** `check_target(info, 10)` is called
- **THEN** `UnsupportedFormatError` is raised and no header version is returned

#### Scenario: Unsupported target
- **GIVEN** a board read at `20241229`
- **WHEN** `check_target(info, 8)` is called
- **THEN** `ValueError` is raised listing the supported targets

