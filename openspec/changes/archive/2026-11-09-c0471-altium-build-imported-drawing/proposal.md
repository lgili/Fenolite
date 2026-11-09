# c0471: build --target altium writes an imported Altium drawing directly

## Why

Change c0470 taught `fenolite import --to python` of an Altium project with sheets to emit `schematic.toml`
with the source drawing, including multi-line opaque subtrees (`OWNERINDEX=@<line>`, e.g. parameter sets,
directives, harness connectors and their entries), harness records (`215`, `216`, `217`, `218`, and harness
ports `18`) and non-electrical annotation records (`209` `Note`, `225` `CompileMask`). Building the emitted
code for KiCad (`fenolite build code/design.py`) and converting the built project to Altium
(`fenolite convert --to altium`) works and reproduces the source drawing at level S.

However, building the emitted code directly for Altium (`fenolite build code/design.py --target altium`)
fails on projects that hold any of those records:

1. `backends/altium/drawn.py` only accepts multi-line opaque subtrees (`OWNERINDEX=@<line>`), harness opaque
   records, and `_carried_harnesses` stand-in pruning when `carry=True` (the `convert` path), while
   `lens/altium.py` calls `lower_drawn` with `carry=False`. Any parameter set (`RECORD=43` with child
   `RECORD=41`) or harness connector (`RECORD=215` with child `216`/`217`) in `schematic.toml` therefore
   raises `FEN-3004` ("opaque Altium text must be a root graphic, without ownership, electrical or
   framework-owned records").
2. `_read_native` in `backends/altium/drawn.py` refuses any written `.SchDoc` that contains an
   `UnknownRecord`, even when that record is an opaque `Note` (`RECORD=209`) or `CompileMask` (`RECORD=225`)
   that `drawn_read` extracted from an Altium sheet (`drawn_read.record_class`).

## What Changes

1. **Opaque subtrees and harness records in `lower_drawn`.** `backends/altium/drawn.py` accepts multi-line
   opaque subtrees whose children reference an earlier line of the same opaque item with `OWNERINDEX=@<line>`,
   writes opaque harness records (`drawn_read.is_harness_text`) with UTF-8 twins when needed (`read=True` for
   multi-line/harness opaque items), and runs `_carried_harnesses` stand-in pruning whenever a sheet holds
   carried harness opaque records, whether `lower_drawn` was called by `convert` (`carry=True`) or by
   `build --target altium` (`carry=False`). Single-line root records in `_MODELLED` (except harness ports)
   and raw numeric `OWNERINDEX` fields remain refused with `FEN-3004`.
2. **Note and CompileMask records in `_read_native`.** `_read_native` in `backends/altium/drawn.py` allows
   `UnknownRecord` instances whose `RECORD` is `209` (`Note`) or `225` (`CompileMask`), matching
   `drawn_read.record_class`, while still refusing any other `UnknownRecord`.

## Non-goals

- Changing `carry=False` on `build --target altium` for KiCad-only carrier parameters (`Fenolite.KiCad.Sheet`
  stays conversion-only when needed).
- Adding new record classes to `RECORD_TYPES`.
