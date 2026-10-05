## ADDED Requirements

### Requirement: Alias resolution
`fenolite.lens.moved` SHALL resolve the aliases of a build: `resolve_aliases(design, board, *, moves, module_moves, net_moves) -> tuple[Aliases, tuple[Issue, ...]]`, with `Aliases(parts, modules, nets, explicit_nets)`, and `identity_map(old, new, locators) -> Mapping[str, str]`.
- The module MUST import only the standard library, `core`, `model` and `backends`, and every function MUST be pure.
- `parts` MUST equal `moves`, the expanded part aliases of `dsl.moves` (new path → old path), and `modules` MUST equal `module_moves` (`design-dsl`, "Path aliases in the DSL").
- `nets` (new name → old name) MUST hold every entry of `net_moves` whose old name is a net of `board`. For every other net of `board` whose name is not a net of `design` and starts with `<old>/` for a module alias `new → old`, it MUST hold `<new>/<rest> → <name>` when `<new>/<rest>` is a net of `design` that no entry of `net_moves` names. When several module aliases apply, the longest `old` MUST win.
- `explicit_nets` MUST be the keys of `nets` that come from `net_moves`.
- An entry of `net_moves` whose old name is not a net of `board` MUST give `layout.net-alias-unused` (warning) naming both names. With `board=None`, `nets` MUST be empty and no issue given.
- `identity_map(old, new, locators)` MUST return `{embed.placement_uuid(old, loc): embed.placement_uuid(new, loc)}` for every locator given.
- `result.preserved` MUST gain `module_aliases` (new module path → old) and `net_aliases` (new name → old), empty without an existing board; "Layout preservation evidence" allows the keys.

#### Scenario: Module alias with its nets
- **GIVEN** a design holding `Module("supply")` with parts `R1` and `R2` and the net `supply/FB`, with `d.moved("power", "supply")`, and a board holding the net `power/FB`
- **WHEN** `resolve_aliases` runs with the values of `dsl.moves`, `dsl.module_moves` and `dsl.net_moves`
- **THEN** `parts` is `{"supply/R1": "power/R1", "supply/R2": "power/R2"}`, `nets` is `{"supply/FB": "power/FB"}`, `explicit_nets` is empty and no issue is given

#### Scenario: An explicit net alias wins
- **GIVEN** the same design with its net renamed `supply/VFB` and `d.moved_net("power/FB", "supply/VFB")`
- **WHEN** the aliases are resolved
- **THEN** `nets` is `{"supply/VFB": "power/FB"}` and `explicit_nets` is `("supply/VFB",)`

#### Scenario: Explicit alias without a board net
- **GIVEN** `d.moved_net("VX", "VY")` and a board without a net `VX`
- **WHEN** the aliases are resolved
- **THEN** `nets` is empty and the issues hold one `layout.net-alias-unused` naming `VX` and `VY`

#### Scenario: Identity map
- **WHEN** `identity_map("R1", "R7", ["/footprint", "/footprint/pad[0]"])` is called
- **THEN** it maps `placement_uuid("R1", "/footprint")` to `placement_uuid("R7", "/footprint")` and `placement_uuid("R1", "/footprint/pad[0]")` to `placement_uuid("R7", "/footprint/pad[0]")`, and holds nothing else

### Requirement: Placement extraction
`fenolite.lens.extract.extract_placements(board, match, *, design) -> Extracted` SHALL give the placement of every matched footprint that lies on the board, with `Extracted(placements, unplaced)`.
- `placements` MUST map each component path of `match.matches` whose footprint is not off the board ("Placement precedence") to a `SourcePlacement` ("Placements file") with the footprint's position in the written frame, its rotation, its side and its lock, in path order.
- `unplaced` MUST list the other matched paths, in path order: a staged part copied into the file would look placed and lose its `layout.unplaced` warning.
- Orphans and board-only footprints MUST NOT be extracted.
- The function MUST be pure and MUST import neither `geometry` nor `dsl`.

#### Scenario: Moved footprint extracted
- **GIVEN** the board of a target-10 blink build edited by `edit_blink`, read with `read_board`, and its match
- **WHEN** `extract_placements` runs
- **THEN** `placements` holds `D1`, `R1` and `U1`, the entry of `D1` is 4 mm right of its `place()` position in the written frame, and `unplaced` is empty

#### Scenario: Staged part not extracted
- **GIVEN** the board of a blink variant whose `R1` has no `place()` and is staged beside the outline
- **WHEN** `extract_placements` runs
- **THEN** `placements` holds no `R1`, and `unplaced` is `("R1",)`

### Requirement: Placements file
`fenolite.lens.placements` SHALL read and write `placements.toml`, the committed copy of a layout's placements, with `SCHEMA = "fenolite.placements.v0"`, `FILE_NAME = "placements.toml"`, `SourcePlacement(at, rotation, side, locked)`, `PlacementsFile(entries, issues)`, `read_placements(text, *, origin, file="") -> PlacementsFile` and `write_placements(entries, *, origin) -> str`.
- **Form.** The top-level key `schema` MUST be `SCHEMA`. Each entry MUST be a table `[part."<component path>"]` with the keys `x` and `y` (millimetres, both required), `rotation` (degrees, default 0), `side` (`"top"` or `"bottom"`, default `"top"`) and `locked` (boolean, default false). No other key is allowed.
- **Frame.** `x` and `y` are the position in the frame of `place()`: `SourcePlacement.at` MUST be `origin` plus (`x`, `y`) on reading, and `write_placements` MUST print `at` minus `origin`. Callers pass `dsl.BOARD_ORIGIN`.
- **Values.** The text MUST be read with `tomllib` and `parse_float=Decimal`, so no float is created. `x` and `y` MUST be whole nanometres and `rotation` whole microdegrees in [0, 360). `locked` is the footprint's lock in KiCad, never a precedence ("Placement precedence").
- **Errors.** A text that is not TOML, or whose `schema` is missing or differs, MUST raise `FormatError` (`FEN-3004`) naming `file`. A table whose path is not a component path, an unknown key, a missing `x` or `y`, a value off its unit or of the wrong type, or a `side` other than the two names MUST give `layout.source-invalid` (error) naming the table and the key, and that entry MUST be left out.
- **Printing.** `write_placements` MUST write the comment `# Written by fenolite sync --to-source.`, the `schema` line, an empty line, then one table per entry in component-path order, each with `x`, `y`, `rotation`, `side` and `locked` in this order. Numbers MUST be printed in their shortest exact decimal form (`30`, `12.7`, `-0.000001`). Nothing MUST depend on the clock, the platform or `PYTHONHASHSEED`.
- **Round trip.** `read_placements(write_placements(entries, origin=o), origin=o).entries` MUST equal `entries` for every mapping of component paths to whole-unit placements.

#### Scenario: Position in millimetres
- **GIVEN** the text `schema = "fenolite.placements.v0"`, `[part."power/R1"]`, `x = 12.7`, `y = 30`, `rotation = 90`
- **WHEN** it is read with `origin` (100 mm, 100 mm)
- **THEN** `power/R1` has `at == Point(112_700_000, 130_000_000)`, rotation `90_000_000`, side `top` and `locked` false, and no issue is given

#### Scenario: Value off the nanometre
- **GIVEN** an entry with `x = 1.0000005`
- **WHEN** it is read
- **THEN** the issues hold one `layout.source-invalid` naming the table and `x`, and the entry is left out

#### Scenario: Missing schema
- **GIVEN** a text with one table and no `schema` key
- **WHEN** it is read with `file="placements.toml"`
- **THEN** `FormatError` is raised naming `placements.toml`

#### Scenario: Round trip
- **WHEN** `uv run pytest tests/unit/lens/test_placements_file.py -k round_trip` runs its property test over generated entries
- **THEN** every printed text reads back to its entries, and printing them again gives the same text

### Requirement: Symbol placement extraction
`fenolite.lens.schplacements` SHALL gain `extract_symbol_placements(sheets, *, design) -> tuple[Mapping[str, SymbolPlacement], tuple[Issue, ...]]` and `write_placements(entries) -> str`, which turn the symbols of a generated schematic, as edited in KiCad, into the text of `schematic-placements.toml` that `read_placements` reads (`design-dsl`, "Schematic placements file", c0061).
- `sheets` MUST be the sheets that `sch.read_schematic` (c0060) gives for the root file and for every child sheet file it names.
- Each placed symbol unit whose `fenolite.path` property is a component path of `design` MUST give an entry keyed `<path>` for unit 1 and `<path>#<unit>` above it, with its position, rotation and mirror. Symbols without that property, power flags included, MUST give no entry and no issue.
- A position off the 1.27 mm grid, or a (rotation, mirror) pair outside `schlayout.PROVED_FRAMES`, MUST give `sync.symbol-off-grid` (warning) naming the key, and no entry.
- `write_placements` MUST print one table per entry in key order, with `x` and `y` in millimetres in their shortest exact decimal form, then `rotation` when it is not 0 and `mirror` when the symbol is mirrored. `read_placements` of the text MUST give the entries back.

#### Scenario: Moved symbol extracted
- **GIVEN** the schematic of a target-10 blink build whose symbol `R1` was moved 2.54 mm to the right by token edit, read with `sch.read_schematic`
- **WHEN** `extract_symbol_placements` runs and its entries are printed and read back with `read_placements`
- **THEN** `R1` is 2.54 mm right of its generated position, no issue is given, and the read-back entries equal the extracted ones

#### Scenario: Symbol off the grid
- **GIVEN** the same schematic with `R1` moved 1 mm instead
- **WHEN** `extract_symbol_placements` runs
- **THEN** the result has no `R1` entry, and the issues hold one `sync.symbol-off-grid` naming `R1`

### Requirement: Sync of the source tree
`fenolite.lens.sync.plan_sync(design, existing, *, name, aliases, origin, placements_text, symbol_placements_text, sheets) -> SyncPlan` SHALL compute what `fenolite sync --to-source` writes and reports, without reading or writing a file, with `SyncPlan(files, result, issues)`.
- `existing` MUST be the `ExistingProject` of the output folder; its board text MUST be present, and the board MUST be read, refused and matched as "Existing project files" and "Footprint matching" do, with `aliases.parts`.
- `files` MUST map `placements.toml` to `write_placements(extract_placements(…).placements, origin=origin)` when that text differs from `placements_text` (`None` when the file does not exist). When `sheets` is given, it MUST map `schematic-placements.toml` to the printed symbol placements when that text differs from `symbol_placements_text`.
- `result` MUST hold `board` (the file name), `placements` (the number of entries), `unplaced`, `orphans` and `board_only` (references), `symbols` (the number of symbol entries, or `null` without `sheets`) and `files` (the names in `files`).
- The issues MUST use only the codes of the closed table `SYNC_ISSUE_CODES`, besides those of the board read and of "Symbol placement extraction":

| code | severity | when |
|---|---|---|
| `sync.would-change` | error | with `--check`, a file would change |
| `sync.orphan` | warning | a footprint with `fenolite.path` matches no part; the next build removes it |
| `sync.net-dropped` | warning | the board holds copper on a net that no design net or alias covers; the next build drops it |
| `sync.value-differs` | warning | the board's value, library footprint or user property of a matched part differs from the script's; the next build writes the script's |
| `sync.symbol-off-grid` | warning | a symbol's position or frame cannot be written to `schematic-placements.toml` |

- `sync.would-change` MUST be added by the command, not by `plan_sync`, and MUST name the file and its first table whose text differs.
- `lens.sync.EVIDENCE` MUST equal `lens.preserve.EVIDENCE`.

#### Scenario: Edited board synced
- **GIVEN** a confirmed target-10 blink build in `B` edited by `edit_blink`, and no `placements.toml`
- **WHEN** `plan_sync` runs with `placements_text=None`
- **THEN** `files` holds `placements.toml` with tables for `D1`, `R1` and `U1`, `D1` at `x` 4 mm more than its `place()` value, and no issue is given

#### Scenario: Nothing to write
- **GIVEN** the same build and the text that the first run printed as `placements_text`
- **WHEN** `plan_sync` runs again
- **THEN** `files` is empty

#### Scenario: Orphaned complement reported
- **GIVEN** the same edited board and a `design.py` without `R1`, whose `D1` pin 2 is connected to nothing
- **WHEN** `plan_sync` runs
- **THEN** the issues hold `sync.orphan` naming `R1`, and `sync.net-dropped` naming `LED_A` with its 2 tracks and 1 via

#### Scenario: Value edited in KiCad
- **GIVEN** the same build whose board gets `R1`'s value `4k7` by token edit, while `design.py` keeps `330`
- **WHEN** `plan_sync` runs
- **THEN** the issues hold one `sync.value-differs` naming `R1`, `value`, `4k7` and `330`

#### Scenario: Closed set
- **WHEN** `uv run pytest tests/unit/lens/test_sync.py -k closed_set` collects the codes produced by its tests
- **THEN** each `sync.*` code is a key of `SYNC_ISSUE_CODES` with the severity of the table, and every key is produced by at least one test

### Requirement: Lens acceptance fixture
`tests/unit/lens/test_lens_acceptance.py` SHALL run the plan's lens acceptance on a design authored for Fenolite, for targets 9 and 10, and every check of this requirement MUST hold.
- **Fixture.** `tests/data/lens/acceptance/design.py` MUST use only parts of the Mini test libraries. It MUST hold a part `U1` at the top and two modules, `power` and `io`, with at least three parts each, every part placed by `place()`, and module-local nets named `f"{m.path}/<name>"`, among them `power/FB`.
- **Edits in place of the GUI**, by token edit of the built board with `tests/_layout_edit.py`: five footprints moved by distinct offsets, three of them in `power`; three tracks with version-4 uuids, from pad to pad, on `power/FB`, on a net of `io` and on a top-level net; the `Reference` property of one `power` footprint moved by 1 mm; and a root `group` with a version-4 uuid holding two `power` footprints. When c0061 is archived, the board then passes through `update_from_schematic`.
- **Script edits**: a part `R9` added to `io` without `place()`, and the module `power` renamed `supply` with `d.moved("power", "supply")`.
- **Checks after the rebuild**: every moved footprint has its edited position and rotation; the three tracks keep their uuids, ends, widths and layers, the first on `supply/FB`; the moved `Reference` property is tree-equal to the edited one after the identity map; the group lists the two renamed footprints by their new uuids; `R9` is staged with `layout.unplaced`; `issues` hold no `layout.orphan`, `layout.net-removed`, `layout.footprint-replaced` or `zone.fill-stale`; `result.preserved.kept` lists every part but `R9`.
- **Normal form**: with the `moved()` call removed, the next build MUST write every file with the bytes of the previous one.
- **Source tree**: `fenolite sync --to-source --confirm` MUST then write `placements.toml`, and a `--discard-layout` build into an empty folder MUST place every footprint that was on the board at its edited position.

#### Scenario: Everything preserved through a module rename
- **WHEN** `uv run pytest tests/unit/lens/test_lens_acceptance.py -k rename` runs for targets 9 and 10
- **THEN** every check of the rebuild holds, and the build after the `moved()` call is removed writes the same bytes

#### Scenario: Layout restored from the source tree
- **GIVEN** the rebuilt folder of that test and the `placements.toml` that `sync` wrote
- **WHEN** the design is built with `--discard-layout` into an empty folder
- **THEN** every footprint that was on the board is at its edited position, and `R9` is staged

#### Scenario: After the stand-in update
- **GIVEN** c0061 archived, and the edited board passed through `update_from_schematic` before the script edits
- **WHEN** the same test runs
- **THEN** every check still holds, and the footprints keep their `sheetname` and `sheetfile` children

### Requirement: Complete lens is documented
The additions of this change SHALL be documented in Fenolite's own words.
- `docs/lens.md` MUST gain the sections "Module aliases", "Net aliases", "Renamed footprints keep their edits" (the identity map, group members, and DRC exclusions that have to be made again), "placements.toml" (form, frame, precedence, `--discard-layout`) and "sync" (both files, `--check`, the issues), and its precedence and issue tables MUST match "Placement precedence" and "Layout issue codes".
- `docs/dsl.md` MUST describe `moved()` on module paths and `moved_net()`.
- `docs/hypotheses.md` MUST register `H-K-LENS-RENAME` (backend `kicad`, level `INFERRED`, the test of "Renamed footprints pass the oracle").

#### Scenario: Register holds the new row
- **WHEN** `grep -c '^| H-K-LENS-RENAME ' docs/hypotheses.md` runs
- **THEN** it prints `1`, and `uv run pytest tests/unit/test_hypotheses_register.py` passes

## MODIFIED Requirements

### Requirement: Existing project files
`lens.preserve.read_existing(out_dir, name) -> ExistingProject` SHALL return the texts of `<name>.kicad_pcb`, `<name>.kicad_pro` and `<name>.kicad_dru` in `out_dir`, each `None` when the file does not exist, and `build` SHALL preserve the layout from them unless `--discard-layout` is given.
- The texts MUST be read as UTF-8; a file that does not decode MUST raise `FormatError` (`FEN-3004`) naming it.
- `prepare(design, placements, existing, *, name, moves={}, module_moves={}, net_moves={}, source={}) -> Prepared` MUST read the board text with `read_board(text, file="<name>.kicad_pcb")`, so the relative file name, never an absolute path, reaches provenance. It MUST resolve the aliases with `lens.moved.resolve_aliases` ("Alias resolution"), match with their `parts`, and pass `source` to `effective_placements`. `Prepared.aliases` MUST stay the part aliases, and `Prepared.net_aliases` and `Prepared.module_aliases` MUST hold the resolved `nets` and `modules`. Reader warnings MUST go to `Prepared.issues`; reader infos MUST only be counted in the build summary.
- Refusals MUST happen before any planned write, so `--dry-run` refuses too: a board that does not parse (`FEN-3004`); a board whose header is newer than every known version, a project file of an unknown version or a rules file of version 2 or more (`FEN-3002`, `FEN-3003`); a KiCad 8 board (`FEN-7003`, c0017); a board of major 10 built for target 9 (`DowngradeRefusedError`, `FEN-7002`, c0017); a rules file that `parse_rules` refuses (`FEN-3004`, with the line).
- With `--discard-layout`, none of the three files MUST be read: the build is a fresh build, and the mutation protocol keeps a `.bak` of every replaced file unless `--no-backup` is given.

#### Scenario: Missing files
- **GIVEN** a folder holding only `blink.kicad_pro`
- **WHEN** `read_existing(folder, "blink")` is called
- **THEN** the result has `board is None`, `rules is None` and the project text

#### Scenario: Discarding the layout
- **GIVEN** a confirmed target-10 blink build in `B` whose board was replaced by `tests/_layout_edit.py::edit_blink` of its text
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --discard-layout --confirm` runs
- **THEN** the exit code is 0, `B/blink.kicad_pcb` is byte-equal to a build into an empty folder, and `B/blink.kicad_pcb.bak` holds the edited board

#### Scenario: Board of major 10 built for target 9
- **GIVEN** a confirmed target-10 blink build in `B`
- **WHEN** `fenolite --kicad-version 9 build examples/blink_2layer/design.py --out B --dry-run --json` runs
- **THEN** the exit code is 7, stderr carries `FEN-7002`, and no file under `B` changes

#### Scenario: Broken rules file
- **GIVEN** a confirmed blink build in `B` whose `blink.kicad_dru` gets the rule `(rule 'big one' (constraint clearance (min 1mm)))` as its third line
- **WHEN** the build runs again with `--dry-run --json`
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and its `where` names `blink.kicad_dru` and `line 3`

### Requirement: Placement precedence
`lens.preserve.effective_placements(placements, match, *, design, board, source={})` SHALL decide each part's placement with the fixed precedence: a locked `place()`, then the existing board, then the part's entry in the placements file (`source`, "Placements file"), then `place()`, then the build's staging (later, c0022's placer). `prepare` SHALL call it, and `cmd_build` SHALL pass the result to `build_design` as its `placements`.
- `placements` MUST be `dsl.placements(design)` (c0011): component path → an object with `at`, `rotation`, `side` and `locked`. "Locked" means `place(…, locked=True)` in the script.
- `source` MUST map component paths to `SourcePlacement` entries. An entry that wins MUST be given as a `KeptPlacement` with the entry's position, rotation, side and lock, so the build writes the entry's lock; that lock gives the entry no precedence.
- For a matched part: a locked `place()` MUST win. Otherwise, when its footprint is off the board, the part's `source` entry MUST win, then its `place()`, and without either the part MUST be left unplaced, so the build stages it again (`layout.unplaced`). Otherwise the footprint's own position, rotation, side and lock MUST be used, as a `KeptPlacement`.
- A footprint is off the board when its position lies outside the closed bounding box of the points of `design.board.outline`, and only when the board's edge content is absent or is exactly that outline ("Board content outside the design is kept"). Otherwise no footprint counts as off the board.
- For an unmatched part: a locked `place()`, then its `source` entry, then its `place()`; otherwise it is left unplaced and staged by the build.
- Without an existing board, `prepare` MUST return what `effective_placements` gives with an empty match and `board=None`, which is `placements` unchanged when `source` is empty, and no match. With `board=None` no footprint is off the board, and a design without an outline has none either.
- An unlocked `place()` whose position, rotation or side differs from a kept board placement MUST give `layout.place-overridden` (info), naming the part and both placements, with the hint "lock the placement in the script, move the footprint in KiCad, or re-run with --discard-layout". When it differs from a `source` entry that wins, the same code MUST be given with the hint "lock the placement in the script, or edit placements.toml".
- A `source` entry of a part that keeps a board placement different from the entry MUST give `layout.source-stale` (info) naming the part and both placements, with the hint "run fenolite sync --to-source". An entry that names no part of the design MUST give `layout.source-unknown` (warning).
- A locked `place()` that differs from the board's position, rotation, side or lock MUST give `layout.place-forced` (warning), because the footprint is then re-placed from its definition ("Kept and re-placed footprints").

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
- **GIVEN** the board edited by `edit_blink` and a `source` entry for `D1` at its `place()` position
- **WHEN** `effective_placements` runs
- **THEN** `D1` keeps its board placement, and the issues hold one `layout.source-stale` naming `D1`

#### Scenario: A locked footprint in the file
- **GIVEN** no existing board and a `source` entry for `R1` with `locked = true`
- **WHEN** the blink is built
- **THEN** `R1` is written at the entry's position with `(locked yes)`, and a later edit of the board still wins over the entry

### Requirement: Kept and re-placed footprints
`lens.preserve.merge_layout(built, board, match) -> Merged` SHALL keep the existing board's own footprint node for every matched part that stays where the board has it, and SHALL use the built copy otherwise.
- A matched footprint MUST be kept when its key is `uuid`, `path` or `alias`, its `lib_ref` equals the built component's `lib_footprint_ref`, and the built copy has the footprint's position, rotation, side and lock.
- A kept footprint MUST keep every slot of its node: properties, texts, graphics and pads as edited in KiCad, except its user properties. Its `component_id` MUST become the built component's id, and each pad MUST take the net of the built copy's pad with the same number, or none. The component MUST take the projected `properties` of the kept node, its user properties included, so c0017's "Projected fields on write" passes, and keeps the built `ref` and `value`, which c0017's writer writes into the Reference and Value atoms.
- **User properties belong to the script** (`design-dsl`, "User properties on built footprints"). They are the `property` nodes that the built copy holds after its `fenolite.path` node. For each of them, the kept node's `property` node whose name is equal after `str.casefold()` MUST take its name and value and keep every other child, its uuid, position and visibility included. A missing one MUST be appended after the kept node's last `property` node as the built copy has it, with the uuid `embed.placement_uuid(<component path>, "/footprint/property:<name>")`, which no index-derived uuid equals. A property that the script does not name stays, because one added in KiCad cannot be told from one that the script no longer names. Without a `fenolite.path` node (`H-K-BUILD-PATHPROP` refuted), the kept node keeps its properties.
- **A footprint kept through an alias** MUST take the new identity of its part. Its identity map is `lens.moved.identity_map(old, new, locators)` ("Alias resolution"), where `locators` are the locators of every node of the built copy that holds a `uuid` child. Every `uuid` child of the kept node whose text is a key of the map MUST take the mapped text, and every other `uuid` child MUST stay. Its `fenolite.path` property MUST take the new path. Its `path`, `sheetname` and `sheetfile` children MUST take the built copy's when the built copy has them, and otherwise stay. It MUST give `layout.alias-used` (info) naming both paths and the word `kept`.
- Any other matched footprint MUST be replaced by the built copy, c0011's placed copy at the effective placement, keyed by the component path: with `layout.alias-used` (info) naming both paths and the word `replaced` for an alias match, `layout.footprint-replaced` (warning) when the lib id changed, and `layout.place-forced` from "Placement precedence".
- Footprints MUST keep the board's order; new and re-placed built copies follow in component-path order.
- Later requirements MAY change named slots of a kept node or of a re-placed built copy, such as its fields; each such requirement names this one.

#### Scenario: Silkscreen edit kept
- **GIVEN** the edited target-10 blink board, whose `Reference` property of `R1` is also moved 1 mm by token edit
- **WHEN** the build runs again
- **THEN** that property node is tree-equal to the edited one, and `R1` is listed under `result.preserved.kept`

#### Scenario: Value changed in the script
- **GIVEN** the same board and `R1`'s value set to `4k7` in `design.py`
- **WHEN** the build runs again
- **THEN** `R1`'s `Value` property holds `4k7` and is otherwise tree-equal to the edited node

#### Scenario: User property changed in the script
- **GIVEN** a confirmed target-10 build of a blink variant whose `R1` has `properties={"Part number": "PN-330"}`, whose board then gets `R1`'s `Reference` property moved 1 mm by token edit, after which `design.py` sets `Part number` to `PN-470` and adds `"Supplier code": "S-1"`
- **WHEN** the build runs again and the written board is read with `read_board`
- **THEN** `R1` is listed under `result.preserved.kept`, its `Reference` node is tree-equal to the edited one, its `Part number` node holds `PN-470` with its former uuid and position, a `Supplier code` node follows it, and the read-back `R1` has both values

#### Scenario: Property added in KiCad kept
- **GIVEN** a confirmed blink build whose board gets a hidden property `Note` on `R1` by token edit
- **WHEN** the build runs twice
- **THEN** both builds keep the `Note` node, and the second writes every file with the bytes of the first

#### Scenario: Footprint changed in the script
- **GIVEN** the same board and `R1`'s footprint changed in `design.py` to `Mini:Mini_LED_THT_3mm`
- **WHEN** the build runs again
- **THEN** `R1`'s footprint is `Mini:Mini_LED_THT_3mm` at the position, rotation and side `R1` had on the board, and `issues` holds `layout.footprint-replaced` naming `R1`

#### Scenario: Rename through an alias
- **GIVEN** a confirmed blink build, after which `design.py` renames `R1` to `R7` and calls `d.moved("R1", "R7")`
- **WHEN** the build runs again, and once more after the `moved()` call is removed
- **THEN** the first rebuild keeps the board node of `R1` for `R7`, where `R1` was, with uuid `footprint_uuid("R7")`, `fenolite.path` `R7`, every pad uuid derived from `R7`, `R7` under `result.preserved.kept` and `layout.alias-used`, and the second rebuild matches `R7` by uuid and writes the same bytes

#### Scenario: Silkscreen edit survives a rename
- **GIVEN** a confirmed target-10 blink build whose `Reference` property of `R1` is moved 1 mm by token edit, after which `design.py` renames `R1` to `R7` and calls `d.moved("R1", "R7")`
- **WHEN** the build runs again
- **THEN** the `Reference` node of `R7` is tree-equal to the edited node of `R1` except for its uuid, which is `placement_uuid("R7", <its locator>)`

#### Scenario: Item added in KiCad keeps its uuid
- **GIVEN** the same build whose footprint of `R1` gets, by token edit, an `fp_line` on `F.SilkS` with the uuid `00000000-0000-4000-8000-0000000000e1`, and the same rename
- **WHEN** the build runs again
- **THEN** the footprint of `R7` holds that line with that uuid

#### Scenario: Alias with a new footprint is re-placed
- **GIVEN** the same rename, with `R7`'s footprint changed in `design.py` to `Mini:Mini_LED_THT_3mm`
- **WHEN** the build runs again
- **THEN** `R7` is the built copy at `R1`'s board placement, `issues` hold `layout.alias-used` with the word `replaced` and `layout.footprint-replaced`

### Requirement: Copper items follow their nets
`lens.preserve.merge_layout` SHALL keep every track, arc, via and zone of the existing board, with all its slots, when it has no net, when its net name is a net of the built design, or when its net name is the old name of a resolved net alias ("Alias resolution") whose new name is a net of the built design, and SHALL drop it otherwise.
- A kept item MUST take the built design's net of the same name, or of the alias's new name; its uuid and every other slot MUST stay unchanged. A pad of a board-only footprint on the old name of a net alias MUST take the new net.
- Each net alias under which at least one item or pad was kept MUST give one `layout.net-alias-used` (info) naming both names and the counts of tracks, arcs, vias, zones and pads.
- Each net that loses items MUST give one `layout.net-removed` (warning) naming the net and the counts of dropped tracks, arcs, vias and zones and of board-only footprint pads left without a net.
- Rule areas (`Keepout`) MUST be kept unchanged.
- Later requirements MAY take named items out of this rule, such as copper or zones that the script declares; each such requirement names this one and the items it takes, and those items follow it instead.

#### Scenario: Tracks intact
- **GIVEN** a confirmed target-9 blink build whose board was edited by `edit_blink`
- **WHEN** the build runs again and the written board is read with `read_board`
- **THEN** both segments and the via of the edit are present with the same uuids, end points, widths, layers and the net `LED_A`

#### Scenario: Net removed
- **GIVEN** the same edited board and a `design.py` in which `R1` pin 2 and `D1` pin 2 are connected to nothing
- **WHEN** the build runs again
- **THEN** the board holds neither segment nor the via, and `issues` holds one `layout.net-removed` naming `LED_A` with 2 tracks and 1 via

#### Scenario: Renamed net keeps its routing
- **GIVEN** a confirmed target-10 blink build edited by `edit_blink`, after which `design.py` renames the net `LED_A` to `LED_ANODE` and calls `d.moved_net("LED_A", "LED_ANODE")`
- **WHEN** the build runs again and the written board is read with `read_board`
- **THEN** both segments and the via of the edit are present with their uuids on `LED_ANODE`, `issues` hold one `layout.net-alias-used` with 2 tracks and 1 via, and no `layout.net-removed`

#### Scenario: Rename without an alias
- **GIVEN** the same edit and rename without the `moved_net()` call
- **WHEN** the build runs again
- **THEN** the board holds neither segment nor the via, and `issues` hold one `layout.net-removed` naming `LED_A`

### Requirement: Board content outside the design is kept
`lens.preserve.merge_layout` SHALL keep the existing board's layers, graphics, texts, rule areas, title block, paper and every opaque root child (setup, stack-up, groups, dimensions and the rest) unchanged, except the group members that follow a renamed footprint, and SHALL keep its edge content in place of the design's outline.
- The layout's `Board` MUST be the existing board with its root slots, so c0017's writer re-emits read content in place.
- Each `members` atom of a root `group` node whose text is a key of the identity map of a footprint kept through an alias ("Kept and re-placed footprints") MUST take the mapped text. No other atom of a group MUST change, and Fenolite MUST NOT add or remove a group.
- When the board holds a `Graphic` on a layer of kind `edge`, every such graphic MUST be kept and the layout's `Board.outline` MUST be `None`. When those graphics are not exactly the lines of the built outline (`line` graphics whose end points, as unordered pairs, equal the outline's edges), `layout.outline-kept` (warning) MUST name both. Without edge graphics, the built outline MUST be used.
- The copper layer names of the board, in table order, MUST equal those of `layers.created_layers(copper)`. Otherwise `layout.copper-mismatch` (error) MUST be given, and nothing is written.

#### Scenario: Board setup kept
- **GIVEN** a confirmed blink build whose board's `setup` child has `(pad_to_mask_clearance 0)` changed to `(pad_to_mask_clearance 0.05)` by token edit
- **WHEN** the build runs again
- **THEN** the written `setup` node is tree-equal to the edited one

#### Scenario: Outline edited in KiCad
- **GIVEN** a confirmed blink build whose right `Edge.Cuts` line is moved 5 mm right, with the top and bottom lines lengthened to meet it, by token edit
- **WHEN** the build runs again
- **THEN** the written edge lines equal the edited ones, `issues` holds `layout.outline-kept`, and the exit code is 0

#### Scenario: Copper count changed in the script
- **GIVEN** a confirmed two-layer blink build and `design.py` changed to `copper=4`
- **WHEN** the build runs again with `--confirm`
- **THEN** the exit code is 5, `issues` holds `layout.copper-mismatch`, and nothing is written

#### Scenario: Group follows a renamed footprint
- **GIVEN** a confirmed target-10 blink build whose board gets, by token edit, a root `group` with the uuid `00000000-0000-4000-8000-0000000000f1` holding the footprints of `R1` and `D1`, after which `design.py` renames `R1` to `R7` with `d.moved("R1", "R7")`
- **WHEN** the build runs again
- **THEN** the group holds `footprint_uuid("R7")` and `D1`'s uuid, in the order of the edited group, and keeps its own uuid

### Requirement: Zone fills and the staleness digest
A rebuild SHALL keep the fills of a kept zone only when `zone_digest` of that zone and `fill_inputs_digest` of the board are both equal for the existing board and for the layout to be written; otherwise `lens.preserve.drop_stale_fills` SHALL drop that zone's fills, set its `filled` to false, and report `zone.fill-stale` (warning).
- `zone_digest(design, zone) -> str` MUST be the SHA-256 hex digest of a canonical text of: the outline points, or, when the outline is empty, the texts of the zone's opaque `polygon` slots; the net name; the layers; the priority; the canonical JSON of `zone.settings.effective()`; and the texts of the zone's other opaque slots (among them fill settings that the reader kept opaque). Fills, `filled`, `locked`, uuids and net forms MUST NOT enter it.
- `fill_inputs_digest(design, *, project, rules) -> str` MUST be the SHA-256 hex digest of a canonical text of: every footprint's `lib_ref`, position, rotation, side and modelled pad fields; every track, arc and via's modelled fields; every zone's `zone_digest`; every rule area; every graphic on a layer of kind `edge` and the outline; the classes, patterns and assignments that c0010's `pro.read_project` gives for `project` (none when `None`); and the texts of the rule items of c0018's `parse_rules(rules)` (none when `None`). Nets MUST enter by name; ids, uuids, provenance and slots MUST NOT enter it, and each collection MUST be sorted.
- The existing board MUST be digested with the existing project and rules texts, after its net names are mapped through the resolved net aliases ("Alias resolution"), and the layout with the texts this build writes. A pure rename therefore keeps the fills; a rename that also moves a pin drops them.
- The digests are text only: `lens` never imports `geometry`.

#### Scenario: Unchanged rebuild keeps fills
- **GIVEN** a confirmed blink build whose board gets, by token edit, a zone on `GND` on `B.Cu` holding two authored `filled_polygon` lists
- **WHEN** the build runs again
- **THEN** both fills are written unchanged and `issues` holds no `zone.fill-stale`

#### Scenario: A removed part drops fills
- **GIVEN** the same filled board and `R1` removed from `design.py`
- **WHEN** the build runs again
- **THEN** the zone is kept without fills and with `filled == False`, and `issues` holds `zone.fill-stale` naming it

#### Scenario: A class change drops fills
- **GIVEN** the same filled board and the clearance of class `PWR` changed from 0.2 mm to 0.3 mm in `design.py`
- **WHEN** the build runs again
- **THEN** the zone is kept without fills and `issues` holds `zone.fill-stale`

#### Scenario: A zone setting change drops fills
- **GIVEN** a confirmed build of the blink pour variant whose zone `GND` is declared with `locked=True` and gets, by token edit, `(fill yes …)` and two authored `filled_polygon` lists, after which `design.py` changes the zone's clearance to 0.4 mm
- **WHEN** the build runs again
- **THEN** the zone is written with the clearance 0.4 mm, without fills and without the `yes` atom of `fill`, and `issues` holds `zone.fill-stale` and `kicad.zone.forced`

#### Scenario: Digests ignore ids and formats
- **GIVEN** the filled board of a target-9 build read with `read_board`, and the same board written by `write_board` for target 10 and read again
- **WHEN** `fill_inputs_digest` and `zone_digest` are computed for both with the same project and rules texts
- **THEN** the digests are equal

#### Scenario: A renamed net keeps its fills
- **GIVEN** the filled board of "Unchanged rebuild keeps fills", after which `design.py` renames `GND` to `GND0` and calls `d.moved_net("GND", "GND0")`
- **WHEN** the build runs again
- **THEN** the zone is written on `GND0` with both fills, and `issues` hold no `zone.fill-stale`

### Requirement: Layout issue codes
`lens.preserve` SHALL report its findings only with the codes of the closed table `PRESERVE_ISSUE_CODES`, which `lens.build.BUILD_ISSUE_CODES` includes; every `kicad.*` code, of the readers, the writers and the backend merges that later requirements call from `merge_layout`, the `rules.*` codes and the `model.*` codes MUST pass through unchanged.

| code | severity | when |
|---|---|---|
| `layout.copper-mismatch` | error | the board's copper layers differ from `board(copper=…)` |
| `layout.source-invalid` | error | a table or key of `placements.toml` is invalid |
| `layout.orphan` | warning | a footprint with `fenolite.path` matched no part and is removed |
| `layout.alias-unused` | warning | a part alias, given or expanded from a module alias, matched nothing, or its part matched by uuid or path |
| `layout.net-alias-unused` | warning | a `moved_net(old, new)` alias names no net of the board |
| `layout.source-unknown` | warning | a table of `placements.toml` names no part of the design |
| `layout.place-forced` | warning | a locked `place()` re-placed a footprint whose board placement differed |
| `layout.footprint-replaced` | warning | the part's footprint lib id changed; the footprint is re-placed |
| `layout.net-removed` | warning | items on a net the design no longer has were dropped |
| `layout.outline-kept` | warning | the board's edge content differs from the design's outline and is kept |
| `zone.fill-stale` | warning | a zone's fills were dropped because a digest changed |
| `layout.place-overridden` | info | an unlocked `place()` differs from the kept board placement or from the `placements.toml` entry that wins |
| `layout.alias-used` | info | a part was matched through an alias and kept or re-placed under its new path |
| `layout.net-alias-used` | info | items of a board net were kept under the net's new name |
| `layout.source-stale` | info | a `placements.toml` entry differs from the kept board placement |
| `layout.board-only` | info | a footprint without `fenolite.path` matched no part and is kept |

#### Scenario: Closed set enforced
- **WHEN** `uv run pytest tests/unit/lens/test_preserve_issues.py -k closed_set` collects every issue code produced by the preservation tests
- **THEN** each code other than `kicad.*`, `rules.*`, `model.*` and the codes of c0011's table is a key of `PRESERVE_ISSUE_CODES` with the severity of this table, and every key is produced by at least one test

#### Scenario: Warnings do not fail
- **GIVEN** the edited blink with `R1` removed from `design.py`
- **WHEN** the build runs with `--confirm`
- **THEN** the exit code is 0 and `issues` holds `layout.orphan`
