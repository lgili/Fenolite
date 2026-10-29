## MODIFIED Requirements

### Requirement: Placement precedence
`lens.preserve.effective_placements(placements, match, *, design, board, source={}, base=None, takes=())` SHALL decide each part's placement: a locked `place()` wins; otherwise the part's *request* (its `source` entry, else its unlocked `place()`, else none) and the existing board are merged per property by the three-way rule of `edit-merge` ("Three-way property merge") against the base record `base` of the output folder, and without a base for the part by the fixed precedence of before: the existing board, then the request, then the build's staging (later, c0022's placer). `prepare` SHALL call it, and `cmd_build` SHALL pass the result to `build_design` as its `placements`.
- `placements` MUST be `dsl.placements(design)` (c0011): component path → an object with `at`, `rotation`, `side` and `locked`. "Locked" means `place(…, locked=True)` in the script.
- `source` MUST map component paths to `SourcePlacement` entries: the position keys of the edits file (`edit-merge`, "Edits file schema"), or the entries of a legacy placements file ("Placements file"). An entry that wins MUST be given as a `KeptPlacement` with the entry's position, rotation, side and lock, so the build writes the entry's lock; that lock gives the entry no precedence.
- `base` MUST be the `BaseRecord` read from the output folder (`edit-merge`, "Base record file"), or `None`. `takes` MUST be the parsed `--take` resolutions (`edit-merge`, "Take option of build").
- **Two properties.** The placement is merged as two properties: `position` (x and y) and `rotation` (rotation and side together, because a side change mirrors the footprint and its rotation then reads differently). The footprint's lock in KiCad is no merged property: a kept placement keeps the board's lock.
- For a matched part: a locked `place()` MUST win. Otherwise, when its footprint is off the board, the part's request MUST win, and without one the part MUST be left unplaced, so the build stages it again (`layout.unplaced`). Otherwise, when `base` holds the part, each property MUST take the result of the three-way rule, where *code* is the request (none when the part has none), *CAD* is the footprint's value and *base* is the part's base entry; a request that was removed from the script (code none, base set) MUST keep the board's value, so removing a request never moves a part. Otherwise (no base for the part) the footprint's own position, rotation, side and lock MUST be used, as a `KeptPlacement`, and `edit.base-missing` (info) MUST be given once per build naming the count of such parts.
- **A footprint locked in KiCad** whose property the code changed while the board kept its base value MUST NOT be moved silently: the property is a conflict with the reason `cad-locked` (`edit-merge`, "Conflict record").
- A property that the code changed over an unchanged board value MUST take the code's value, re-placing the footprint ("Kept and re-placed footprints"), and MUST give `edit.code-wins` (info) naming the part, the property and both values.
- A footprint is off the board when its position lies outside the closed box `outline.outline_box(design)` (`kicad-file-backend`, "Board outline as rings"), which holds the arcs of the outline as well as its points, and only when the board's edge content is absent or is exactly that outline ("Board content outside the design is kept"). Otherwise no footprint counts as off the board.
- For an unmatched part: a locked `place()`, then its `source` entry, then its `place()`; otherwise it is left unplaced and staged by the build.
- Without an existing board, `prepare` MUST return what `effective_placements` gives with an empty match and `board=None`, which is `placements` unchanged when `source` is empty, and no match. With `board=None` no footprint is off the board, a design without an outline has none either, and `base` is not read.
- An unlocked `place()` whose position, rotation or side differs from a kept board placement MUST give `layout.place-overridden` (info), naming the part and both placements, with the hint "lock the placement in the script, move the footprint in KiCad, or re-run with --discard-layout". When it differs from a `source` entry that wins, the same code MUST be given with the hint "lock the placement in the script, or edit edits.toml".
- A `source` entry of a part that keeps a board placement different from the entry MUST give `layout.source-stale` (info) naming the part and both placements, with the hint "run fenolite sync --to-source". An entry that names no part of the design MUST give `layout.source-unknown` (warning).
- A locked `place()` that differs from the board's position, rotation, side or lock MUST give `layout.place-forced` (warning), because the footprint is then re-placed from its definition ("Kept and re-placed footprints").
- A conflict that no `--take` resolves MUST give `sync.conflict` (error), so the build plans no write; the footprint's placement in the returned mapping is then the board's.

#### Scenario: The board wins over place()
- **GIVEN** a confirmed target-10 blink build in `B` whose board was edited by `edit_blink`
- **WHEN** the build runs again with `--confirm`
- **THEN** `D1` stays 4 mm right of its `place()` position, `issues` holds one `layout.place-overridden` naming `D1`, and the exit code is 0

#### Scenario: A locked place() wins
- **GIVEN** a confirmed blink build whose `U1`, locked in `design.py`, was moved 2 mm down in its board by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** `U1` is back at its `place()` position and locked, and `issues` holds `layout.place-forced` naming `U1`

#### Scenario: A staged part placed by the script
- **GIVEN** a confirmed build of a blink variant whose `R1` has no `place()`, so it is staged beside the outline, after which `design.py` gains `r1.place(mm(20), mm(10))`
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` is at (120 mm, 110 mm) and `issues` holds no `layout.unplaced`

#### Scenario: A staged part stays staged
- **GIVEN** the same staged build and `design.py` unchanged
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` keeps its staged position, `issues` holds one `layout.unplaced` naming `R1`, and every file keeps its bytes

#### Scenario: The file places an unmatched part
- **GIVEN** an existing blink board without `R1`'s footprint, a design whose `R1` has an unlocked `place()`, and a `source` entry for `R1` at another position
- **WHEN** `effective_placements` runs
- **THEN** `R1` takes the entry's placement as a `KeptPlacement`, and the issues hold one `layout.place-overridden` with the hint that names `placements.toml`

#### Scenario: The board wins over a stale file
- **GIVEN** the board edited by `edit_blink`, a `source` entry for `D1` at its `place()` position and `base=None`
- **WHEN** `effective_placements` runs
- **THEN** `D1` keeps its board placement, and the issues hold one `layout.source-stale` naming `D1`

#### Scenario: A locked footprint in the file
- **GIVEN** no existing board and a `source` entry for `R1` with `locked = true`
- **WHEN** the blink is built
- **THEN** `R1` is written at the entry's position with `(locked yes)`, and a later edit of the board still wins over the entry

#### Scenario: A part on a round board
- **GIVEN** a confirmed build of a blink variant with `board(outline=shape.circle(mm(20), mm(20), mm(40)))` whose `R1` is placed at (20 mm, 5 mm), then rebuilt with `R1`'s `place()` removed
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` keeps its board position, which lies inside `outline_box` though outside the box of the outline's two vertices, and `issues` holds no `layout.unplaced`

#### Scenario: A changed place() moves an unedited part
- **GIVEN** a confirmed target-10 blink build in `B`, with its base record, after which `design.py` moves `R1`'s unlocked `place()` 3 mm to the right
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `R1` is 3 mm right of its former position, `issues` hold one `edit.code-wins` naming `R1` and `position` and no `layout.place-overridden`, and the tracks of other parts keep their uuids

#### Scenario: A hand move and a script move conflict
- **GIVEN** the same build whose board gets `R1` moved 2 mm down by token edit, after which `design.py` moves `R1`'s `place()` 3 mm to the right
- **WHEN** the build runs again with `--confirm --json`
- **THEN** the exit code is 5, `issues` hold one `sync.conflict` naming `R1#position` with its base, code and CAD positions, and no file changes

#### Scenario: A rotation in the script merges with a hand move
- **GIVEN** the same build whose board gets `R1` moved 2 mm down by token edit, after which `design.py` gives `R1`'s `place()` the rotation 90
- **WHEN** the build runs again with `--confirm`
- **THEN** `R1` is at its board position with the rotation 90, and `issues` hold no `sync.conflict`

#### Scenario: A footprint locked in KiCad is not moved silently
- **GIVEN** the same build whose board gets `(locked yes)` on `R1` by token edit, after which `design.py` moves `R1`'s `place()` 3 mm to the right
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** the exit code is 5 and `issues` hold one `sync.conflict` naming `R1#position` with the reason `cad-locked`

#### Scenario: A board without a base record
- **GIVEN** a confirmed target-10 blink build in `B` whose base record was deleted, as on a board built before this change, edited by `edit_blink`
- **WHEN** the build runs again with `--confirm --json`
- **THEN** `D1` keeps its board placement as before, `issues` hold one `edit.base-missing`, and the written folder holds a base record, so the next build merges three ways

### Requirement: Layout issue codes
`lens.preserve` SHALL report its findings only with the codes of the closed table `PRESERVE_ISSUE_CODES`, which `lens.build.BUILD_ISSUE_CODES` includes; every `kicad.*` code, of the readers, the writers and the backend merges that later requirements call from `merge_layout`, the `rules.*` codes, the `model.*` codes and the codes of `lens.edits.EDIT_ISSUE_CODES` (`edit-merge`, "Edit merge error and warning codes", "Edit merge info codes"), which `BUILD_ISSUE_CODES` also includes, MUST pass through unchanged.

| code | severity | when |
|---|---|---|
| `layout.copper-mismatch` | error | the board's copper layers differ from `board(copper=…)` |
| `layout.source-invalid` | error | a table or key of `edits.toml` or of a legacy `placements.toml` is invalid |
| `layout.orphan` | warning | a footprint with `fenolite.path` matched no part and is removed |
| `layout.alias-unused` | warning | a part alias, given or expanded from a module alias, matched nothing, or its part matched by uuid or path |
| `layout.net-alias-unused` | warning | a `moved_net(old, new)` alias names no net of the board |
| `layout.source-unknown` | warning | a table of `edits.toml` or of a legacy `placements.toml` names no part of the design |
| `layout.place-forced` | warning | a locked `place()` re-placed a footprint whose board placement differed |
| `layout.footprint-replaced` | warning | the part's footprint lib id changed; the footprint is re-placed |
| `layout.net-removed` | warning | items on a net the design no longer has were dropped |
| `layout.outline-kept` | warning | the board's edge content differs from the design's outline and is kept |
| `zone.fill-stale` | warning | a zone's fills were dropped because a digest changed |
| `layout.place-overridden` | info | an unlocked `place()` differs from the kept board placement or from the `edits.toml` or `placements.toml` entry that wins |
| `layout.alias-used` | info | a part was matched through an alias and kept or re-placed under its new path |
| `layout.net-alias-used` | info | items of a board net were kept under the net's new name |
| `layout.source-stale` | info | an `edits.toml` or `placements.toml` entry differs from the kept board placement |
| `layout.board-only` | info | a footprint without `fenolite.path` matched no part and is kept |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/lens/test_preserve_issues.py -k closed_set` collects every issue code produced by the preservation tests
- **THEN** each code other than `kicad.*`, `rules.*`, `model.*`, the codes of `EDIT_ISSUE_CODES` and the codes of c0011's table is a key of `PRESERVE_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test

#### Scenario: Warnings do not fail
- **GIVEN** the edited blink with `R1` removed from `design.py`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 0 and `issues` holds `layout.orphan`

### Requirement: Sync of the source tree
`fenolite.lens.sync.plan_sync(design, existing, *, name, aliases, origin, edits_text, placements_text=None, symbol_placements_text, sheets, base=None) -> SyncPlan` SHALL compute what `fenolite sync --to-source` writes and reports, without reading or writing a file, with `SyncPlan(files, result, issues)`.
- `existing` MUST be the `ExistingProject` of the output folder; its board text MUST be present, and the board MUST be read, refused and matched as "Existing project files" and "Footprint matching" do, with `aliases.parts`. `aliases` holds the script's aliases, with the names of `moved_net()` in `nets`; `plan_sync` MUST resolve them against the board with `resolve_aliases`.
- `base` MUST be the base record of the output folder, or `None` (`edit-merge`, "Base record file"). With `sheets`, the schematic is a second CAD side for the properties it holds (`edit-merge`, "CAD sides of a property").
- `files` MUST map `edits.toml` to `lens.edits.write_edits(…)` of the edits that `lens.edits.capture_edits` gives (`edit-merge`, "Capture of CAD edits") when that text differs from `edits_text` (`None` when the file does not exist). When `edits_text` is `None` and `placements_text` is a legacy placements file, each of its entries whose part the board does not place MUST be carried into the capture as a position edit with the part's current request as its `over`, and `sync.placements-migrated` (info) MUST name `placements.toml` with the hint "delete placements.toml after reviewing edits.toml". `placements.toml` MUST NOT be written. When `sheets` is given, `files` MUST map `schematic-placements.toml` to the printed symbol placements when that text differs from `symbol_placements_text`.
- `result` MUST hold `board` (the file name), `placements` (the number of parts whose position or rotation `edits.toml` holds), `edits` (a sorted list of `"<component path>#<property>"` captured), `pending` (the same form, for code changes that the next build writes over an unchanged CAD value), `conflicts` (the conflict records of `edit-merge`, "Conflict record"), `unplaced`, `orphans` and `board_only` (references), `symbols` (the number of symbol entries, or `null` without `sheets`) and `files` (the names in `files`).
- A conflict MUST give `sync.conflict` (error); then `files` MUST be empty, because a conflict is resolved by a build first (`edit-merge`, "Take option of build").
- The issues MUST use only the codes of the closed table `SYNC_ISSUE_CODES`, besides those of the board read, of `lens.edits.EDIT_ISSUE_CODES` and of "Symbol placement extraction":

| code | severity | when |
|---|---|---|
| `sync.would-change` | error | with `--check`, a file would change |
| `sync.conflict` | error | the code and a CAD side both changed a property since the base, to different values, or a recorded edit is stale (`edit-merge`, "Conflict record") |
| `sync.orphan` | warning | a footprint with `fenolite.path` matches no part; the next build removes it |
| `sync.net-dropped` | warning | the board holds copper on a net that no design net or alias covers; the next build drops it |
| `sync.value-differs` | warning | without a base for the part, the board's value, library footprint or user property of a matched part differs from the script's; the next build writes the script's |
| `sync.symbol-off-grid` | warning | a symbol's position or frame cannot be written to `schematic-placements.toml` |
| `sync.placements-migrated` | info | the entries of a legacy `placements.toml` were carried into `edits.toml` |

- `sync.would-change` MUST be added by the command, not by `plan_sync`, and MUST name the file and its first table whose text differs.
- `lens.sync.EVIDENCE` MUST equal `lens.preserve.EVIDENCE`.

#### Scenario: Edited board synced
- **GIVEN** a confirmed target-10 blink build in `B` edited by `edit_blink`, with its base record, and no `edits.toml`
- **WHEN** `plan_sync` runs with `edits_text=None`
- **THEN** `files` holds `edits.toml` with one table, for `D1`, whose `x` is 4 mm more than its `place()` value and whose `over` table holds the `place()` position, `result.edits` is `["D1#position"]`, and no issue is given

#### Scenario: Nothing to write
- **GIVEN** the same build and the text that the first run printed as `edits_text`
- **WHEN** `plan_sync` runs again
- **THEN** `files` is empty

#### Scenario: Orphaned complement reported
- **GIVEN** the same edited board and a `design.py` without `R1`, whose `D1` pin 2 is connected to nothing
- **WHEN** `plan_sync` runs
- **THEN** the issues hold `sync.orphan` naming `R1`, and `sync.net-dropped` naming `LED_A` with its 2 tracks and 1 via

#### Scenario: Value edited in KiCad
- **GIVEN** the same build whose board gets `R1`'s value `4k7` by token edit, while `design.py` keeps `330`
- **WHEN** `plan_sync` runs with the base record
- **THEN** `edits.toml` holds `value = "4k7"` in the table of `R1` and `value = "330"` in its `over` table, `result.edits` lists `R1#value`, and no `sync.value-differs` is given

#### Scenario: Value edited in KiCad without a base
- **GIVEN** the same edited board and `base=None`
- **WHEN** `plan_sync` runs
- **THEN** the issues hold one `sync.value-differs` naming `R1`, `value`, `4k7` and `330`, whose hint names `fenolite build --take cad:R1#value`, and `edits.toml` holds no `value` key

#### Scenario: Conflict blocks the sync
- **GIVEN** the same build whose board gets `R1`'s value `4k7` by token edit, after which `design.py` sets `470`
- **WHEN** `plan_sync` runs with the base record
- **THEN** the issues hold one `sync.conflict` naming `R1#value` with base `330`, code `470` and CAD `4k7`, and `files` is empty

#### Scenario: Legacy placements migrated
- **GIVEN** the edited build, no `edits.toml`, and the `placements.toml` that `fenolite sync --to-source` wrote before this change
- **WHEN** `plan_sync` runs with that text as `placements_text`
- **THEN** `files` holds `edits.toml` and not `placements.toml`, and the issues hold one `sync.placements-migrated`

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/lens/test_sync.py -k closed_set` collects the codes produced by its tests
- **THEN** each `sync.*` code is a key of `SYNC_ISSUE_CODES` with the severity of the table, and every key is produced by at least one test
