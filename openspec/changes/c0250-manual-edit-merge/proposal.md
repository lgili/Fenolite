## Why

Section 11 and core change G of `docs/research/circuit-as-code.md`. Today the board wins for layout and
`sync --to-source` copies positions into `placements.toml`, but a value, footprint, reference or property
changed in KiCad is reported (`sync.value-differs`) and then overwritten, and a value changed in the
schematic editor is lost when the build regenerates the schematic. The other direction
is weak too: once the board exists, a changed unlocked `place()` is ignored (`layout.place-overridden`),
because a two-way merge cannot tell "moved by hand" from "changed in the script".

## What Changes

- **Three-way merge per property, keyed by component path.**
  - *base* is what the last build was given and wrote.
  - *code* is this build: the script plus `edits.toml`.
  - *CAD* is the edited board and, for values, footprints, references and properties, the schematic.
  - One side changed: it wins. Both changed to the same value: fine. Both changed differently:
    `sync.conflict` (error, exit 5).
  - First properties: `position`, `rotation` (with side), `value`, `footprint`. Then `reference` and
    user properties.
- **Base record `<out>/fenolite-base.json`** (`fenolite.base.v0`), written by every build beside
  `.fenolite/`. The output folder is committed and `.fenolite/` is not, so a clone gives the same result.
- **`edits.toml`** (`fenolite.edits.v0`) beside the script. It replaces and extends `placements.toml`,
  keeps its table form, and records, per edited property, the script value it was made over (`over`), so
  a later change of the script under an edit is a `stale-edit` conflict, not a silent override.
  `placements.toml` stays readable, and `sync` migrates it.
- **`fenolite build --take code|cad|board|schematic[:ID[#PROPERTY]]`** resolves conflicts. `sync` records;
  it never resolves.
- **Locks.** A locked `place()` still forces its position. A footprint locked in KiCad is never moved
  silently: a script change over it is a `cad-locked` conflict. `build --frozen` (c0249) refuses `--take`
  and unrecorded CAD edits.
- **Viewer.** `view --check` marks `sync.conflict` on the footprint. c0245's workbench shows base, code
  and CAD, and offers the two takes through its plan protocol.
- Altium builds apply `edits.toml`. Reading Altium documents as a CAD side is a follow-up.

## Capabilities

### New Capabilities

- `edit-merge`: properties and keys, base record, three-way rule, CAD sides, edits file, property merge
  in a build, conflicts, `--take`, capture, references and properties, codes, evidence, docs, fixture.

### Modified Capabilities

- `layout-lens`: MODIFIED "Placement precedence" (three-way for position and rotation), "Sync of the
  source tree" (writes `edits.toml`, conflicts, migration) and "Layout issue codes" (pass-through).
- `design-dsl`: MODIFIED "Placements file in a build" (reads `edits.toml` first, both targets).
- `cli-contract`: MODIFIED "Sync command".
- `check-overlay`: ADDED "Edit conflicts on the board".

## Non-goals

- No rewriting of the Python script. An agent that wants the edit in code uses `fenolite edit` (c0196).
- No three-way merge of field placement, silkscreen, copper, zones or symbol positions; they keep the
  rules of `docs/lens.md` and `schematic-placements.toml`.
- No Altium CAD side, and no change of the Altium sheet snapshot.

## Evidence level required

`INFERRED` for the merge (Fenolite's own behaviour, proved on token-edited boards and schematics).
`kicad-cli` 9.0.9 and 10.0.6 must load every merged board and schematic and report no new DRC or ERC
finding. The new hypothesis `H-K-EDIT-SCH-VALUE` stays `INFERRED` until a KiCad kit case confirms it.

## Impact

- New: `src/fenolite/lens/edits.py`, its unit and `kicad-cli` tests, `tests/data/lens/edit_merge/`.
- Changed: `lens/preserve.py`, `lens/sync.py`, `lens/build.py`, `lens/altium.py`, `cli/cmd_build.py`,
  `cli/cmd_sync.py`, `view` overlay, `explain.toml`, `docs/lens.md`, `docs/cli-contract.md`,
  `docs/hypotheses.md`, guide pages `recovery.md` and `board-workflow.md`, `tests/data/lens/sync_minimal/`.
- Depends on c0249 (lock and refs) for `reference` edits and `--frozen` only; phase 1 lands without it.
  Step 3 of the batch order.
- Size: about 10 design-days.
