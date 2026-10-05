## Why

A rebuild keeps what was done in KiCad (c0019), with three gaps that c0019 left to v0.2b:

- **A renamed module loses its layout.** `moved()` maps one part path to one part path, and an alias match is re-placed from the library, so its silkscreen and field edits are lost.
- **A renamed net loses its routing** (`layout.net-removed`).
- **The layout has no copy in the source tree.** `--discard-layout` or a new output folder bring back the script's `place()` calls and the staging area.

The plan (D10) gives v0.2b the complete lens: `extract`, `adapt`, `moved()` and `sync --to-source`, which writes a committed `placements.toml` (D1.6); an orphaned complement becomes an issue. Acceptance: move 5 footprints and route 3 tracks in the GUI, add a part, rename a module with `moved()`, and everything is preserved, also after "Update PCB from Schematic".

## What Changes

- **Module aliases.** `d.moved("power", "supply")` accepts module paths; board nets named `power/<rest>` follow the design nets `supply/<rest>`.
- **Net aliases.** `d.moved_net("VIN", "VBUS")`: the copper of the old net takes the new one, and fills stay current.
- **Alias matches are kept.** With an unchanged library footprint and placement, the board node stays; the uuids derived from the old path, `fenolite.path` and group memberships move to the new path.
- **`lens/extract.py`**: the placement of every footprint on the board, in the frame of `place()`.
- **`placements.toml`** (`lens/placements.py`), read by `build` beside the script. Precedence: locked `place()`, board, `placements.toml`, `place()`, staging. It survives `--discard-layout`.
- **`fenolite sync DESIGN --out DIR --to-source [--check]`** (`lens/sync.py`): writes `placements.toml` from the board and `schematic-placements.toml` from the schematic; `--check` exits 5 when a file would change. Its issues list what the next build would drop and the values on which board and script disagree.
- **Acceptance fixture**: two modules, five moves, three tracks, a field edit, a group, the stand-in update, an added part, a renamed module; checked item by item and by KiCad.

Size: 12.5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `layout-lens`: MODIFIED "Existing project files", "Placement precedence", "Kept and re-placed footprints", "Copper items follow their nets", "Board content outside the design is kept", "Zone fills and the staleness digest", "Layout issue codes"; ADDED "Alias resolution", "Placement extraction", "Placements file", "Symbol placement extraction", "Sync of the source tree", "Lens acceptance fixture", "Complete lens is documented".
- `design-dsl`: MODIFIED "Path aliases in the DSL"; ADDED "Net aliases in the DSL", "Placements file in a build".
- `cli-contract`: ADDED "Sync command".
- `kicad-oracle`: ADDED "Renamed footprints pass the oracle".

## Non-goals

- No `adapt.py`: the plan's adapt step is `lens/preserve.py` (design, Decision 1).
- No three-way merge with a stored base: the script stays the authority on what it models, and `sync` reports disagreements.
- No net alias guessed from pins, no rename guessed from positions.
- No rewrite of DRC exclusions in the project file (Open Questions).
- No layout reuse across module instances (v0.5b); no KiCad group written by Fenolite.

## Evidence level required

- Kept aliases and the fixture: `lens.preserve.EVIDENCE` stays `INFERRED`, with a new row `H-K-LENS-RENAME`, settled when 9.0.9 and 10.0.6 load the renamed board with the DRC report of the board before the rename, and a 10.0.6 re-save keeps the group.
- `placements.toml`, extraction and `sync`: mechanical; positions are integers read from the board.

## Impact

- New: `lens/moved.py`, `lens/extract.py`, `lens/placements.py`, `lens/sync.py`, `cli/cmd_sync.py`, `tests/data/lens/acceptance/`.
- Changed: `dsl/design.py`, `dsl/convert.py`, `lens/preserve.py`, `lens/schplacements.py` (c0061), `cli/cmd_build.py`, `tests/_layout_edit.py`, `docs/lens.md`, `docs/dsl.md`, `docs/cli-contract.md`.
- Depends on c0060 and c0061 for the schematic half; without them `sync` writes only `placements.toml` and the fixture skips the stand-in.
