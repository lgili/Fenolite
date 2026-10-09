## Why

Milestone v0.5a (`docs/roadmap.md`, Phase 5: "controlled KiCad downgrade (capability resolver)"; Open decisions row 38), written against `origin/dev` at `f802b60`. Fenolite writes for KiCad 9 and 10, but a file that KiCad 10 saved is never written for KiCad 9:

- `versions.check_target` refuses a target older than the source's major with `DowngradeRefusedError` (`FEN-7002`, exit 7), for every kind; `pro._gate_nine` does the same for a project file; a read schematic is only ever rebuilt at its own version. `docs/formats/kicad/versions.md` says: "Downgrade stays refused until a capability resolver exists." `capabilities` reports `downgrade: "unsupported"`.
- The knowledge exists: the token inventory holds 233 rows with the major that introduced each, 63 of them since KiCad 10 (31 of boards and footprints, 17 of schematics, 8 of symbol libraries, 7 of rules), two form rows, and 11 project keys that only 10 writes; all proved by the token fuzz on 9.0.9 and 10.0.6.
- Measured on 2026-10-09 with the refusal bypassed: the two demo boards of format 10 (of 18) are written for target 9 when every too-new token is dropped, and read back equal to the source at level 5. But the drop is coarse: it removes the outermost opaque node that holds a too-new token, so one 10-only child cost each board its whole `setup` node (stack-up, mask and paste settings), and 633 `tenting` nodes, which KiCad 9 writes in its own form, were dropped instead of rewritten.

## What Changes

- **The capability resolver**: `backends/kicad/data/downgrade.toml`, one row per inventory row and project key newer than a target major, with an action: `rewrite` (written in the older form), `same` (dropped, the value is the older major's behaviour), `presentation` (dropped, the drawing or metadata changes) or `design` (dropped, the manufactured or checked design changes; needs `--allow-lossy`). A row may hold a value condition (`duplicate_pad_numbers_are_jumpers no` is `same`, `yes` is `design`). Every row of the inventory newer than 9 must have a resolver row (closed, tested).
- **Edits at the token's own node**, never at the owning opaque slot.
- **A downgrade on request only**: `write_board`, the footprint and symbol library writers, the schematic re-target and the project writer take `downgrade=True`; without it the refusal stays, with a hint naming `fenolite convert --to kicad --kicad-version 9`. `build --kicad-version 9` on a project saved by KiCad 10 keeps refusing.
- **The downgrade direction of `fenolite convert`**: a KiCad 10 project (board, schematics, project-local libraries, project and rules files) written for KiCad 9, with the resolver's actions as report rows and the verification of c0159.
- `capabilities`: the KiCad backend reports `downgrade: "supported"`, and `conversions` lists the downgrade with its evidence.

Size: 8.5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-version-gating`: MODIFIED "Targets and downgrade refusal"; ADDED "Downgrade resolver", "Downgrade edits".
- `backend-protocol`: MODIFIED "Write capability fields".
- `cli-contract`: MODIFIED "Library errors map to registered codes" (the meaning of `FEN-7002`).
- `design-conversion`: ADDED "KiCad downgrade direction".

## Non-goals

- KiCad 8 output, and any target outside `TARGET_MAJORS`.
- A downgrade inside `build`, `place`, `route` or `fill`: those keep refusing a source saved by a newer major.
- Footprint and symbol libraries outside the project (the official libraries are fetched for a major, never written).
- The defect found on the way: `RoyalBlue54L-Feather` (format 9) is refused even for target 9 (`kicad.board.opaque-net-ref`, 4 items); a follow-up change, named in the design.

## Evidence level required

- Each resolver row: `KICAD-VERIFIED (9.0.x, 10.0.x)` by a bench of its own (the 10 construct written by 10.0.6, downgraded, loaded by 9.0.9 with the DRC or ERC of the source; `H-K-DOWN-ROWS`); a row without its bench stays `INFERRED` and its action is `design` until the bench passes.
- The demo projects of format 10: `KICAD-VERIFIED` that 9.0.9 loads them and that `pcb upgrade` back to 10 gives the source at level 5 (`H-K-DOWN-DEMOS`).

## Impact

- New `backends/kicad/resolver.py`, `data/downgrade.toml`; changed `versions.py`, `_pcbwrite.py`, `pcb.py`, `mod.py`, `sym.py`, `sch.py`, `pro.py`, `dru.py`; `convert/to_kicad.py`.
- No output of a write without `downgrade=True` changes.
