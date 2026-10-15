## Why

A board built from Fenolite's own footprint definitions has no `Reference` and no `Value` on its footprints: those of the built-in catalog (c0075, c0076) and those a script authors with `fenolite.dsl.Footprint` (c0055). Both reach the board through `mod.prepare_authored_definition`, whose slot list holds name, description, kind, pads, graphics and models, and `embed._header` sets the two values only on properties the definition already has.

Measured on 2026-10-05 on `dev` at `1882644`, with `kicad-cli` 10.0.6: a header, a resistor and a LED from the catalog build with exit 0; the board's footprints hold `fenolite.path` as their only property; `fenolite check` reports `netlist.assignment-differs` for the pads `-1` and `-2` and `netlist.uncovered` for every pad of the model. Every reference is empty, so pads of different parts share one name. The build half was repeated on 2026-10-07 on `dev` at `a32dcfa4` with a one-part catalog design: exit 0, `fenolite.path` the only property on the board footprint, no property in `lib/Fenolite.pretty/Chip_0603.kicad_mod`. `mod.py`, `embed.py`, `lens/build.py` and the catalog are the same files at `9aba2dff`, the tip this proposal is written against. `check` was not run again; task 0.1 runs it.

No board made from the catalog alone can pass `check`, and the catalog (100 footprints and 49 symbols at `9aba2dff`) is the only library on a machine without KiCad's libraries. The catalog's tests build such a design (`tests/unit/cli/test_catalog.py`), but none runs `check` on the board it gives.

## What Changes

- **Definitions without a file get the two fields.** `mod.prepare_authored_definition` adds a `Reference` property (`REF**`, `F.SilkS`, above the footprint's extent) and a `Value` property (the footprint's name, `F.Fab`, below it). The vendored `.kicad_mod` carries them.
- **Every placed footprint has both fields.** `embed.place_footprint` adds a missing `Reference` or `Value` to a library footprint as well, with the same placement, and the build says so with one `build.field-added` info per definition.
- **`Part.field(...)` works on these footprints**, as on library ones.
- **A rebuild repairs an older board.** A board written before this change gains the two properties on its next build; placements, pad nets and copper stay.
- **Acceptance for the catalog.** A design that names only catalog ids builds for targets 9 and 10, its nets equal the script's in `check`, and with scripted copper `check` exits 0 on `kicad-cli` 9.0.9 and 10.0.6.
- **The Altium build does not change.** `build --target altium` names each placed component from `Component.ref` and `Component.value` (`backends/altium/lower.py`) and never reads a KiCad `property` slot. The Altium documents of a catalog-only design stay byte-equal, and a test proves it.

Milestone: v0.4 (the agent track). Size: 3.5 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-file-backend`: ADDED "Mandatory fields of a placed footprint".
- `layout-lens`: ADDED "Kept footprints gain missing mandatory fields".
- `dsl-footprint-authoring`: ADDED "Authored footprints carry Reference and Value".
- `fenolite-component-catalog`: ADDED "Catalog-only design passes check".

None of the four names exists in a living spec or in an open change on `dev` at `9aba2dff`. c0126 (open on `dev`) adds "Footprint items projected on request" to `kicad-file-backend`: another requirement, no shared text.

## Non-goals

- No new catalog entry and no change of a land pattern.
- No change to the Altium writers and no change of a byte they write (see "What Changes").
- No change to how fields of library footprints are read, placed or preserved (c0030).
- No `model.empty-ref` validation rule for boards that Fenolite did not build (Open Questions of the design).
- No silkscreen clean-up: a generated `Reference` may lie over a neighbour's courtyard, and the script moves it with `Part.field`.
- No new key in the design model: the two fields are entries of `FootprintInstance.fields`, which exists.

## Evidence level required

- The two properties in the board and in the vendored library: `KICAD-VERIFIED` on 9.0.9 and 10.0.6 through `H-K-FP-FIELDS` (KiCad loads the project, its design-rule check names pads by reference, and it reports no `lib_footprint_issues` and no `lib_footprint_mismatch`).
- The hermetic acceptance (nets of the script equal the nets of the board): the level of the board read, `INFERRED`.
- The placement of the generated fields is a Fenolite choice and carries no label.

## Prerequisites

- `0.3.0` is released from `dev` first. c0126 (open on `dev`) promises that every KiCad output of 0.2.0 stays byte-equal through 0.3.0; this change is the one intended change of those bytes after it, for footprints from the catalog or from `dsl.Footprint` only.
- c0126 and c0123 are archived first: both change `FootprintInstance` and how pins map to pads, and this change adds fields to the instances they define.
- Nothing of c0096, c0097 or c0099, and no other proposal of v0.4.
- Waiting for this change: c0079 (its starter names only catalog ids and must pass `check`), c0080, c0081.

## Impact

- Changed: `src/fenolite/backends/kicad/mod.py` (`prepare_authored_definition`), `src/fenolite/backends/kicad/embed.py` (`default_fields`, `place_footprint`), `src/fenolite/lens/build.py` (`build.field-added`), `src/fenolite/lens/preserve.py` (kept footprints), `src/fenolite/cli/data/explain.toml` (one table), `docs/dsl.md`, `docs/lens.md`, `docs/catalog/README.md`, `docs/cli-contract.md` (one code), `docs/hypotheses.md` (one row).
- New tests: `tests/unit/backends/kicad/test_embed_fields.py`, `tests/unit/cli/test_catalog_only.py`, `tests/kicad/build/test_catalog_only.py`.
- **Built projects change once.** Footprints from the catalog or from `dsl.Footprint` gain two properties in the board, in `lib/<nickname>.pretty/` and, as two entries of an existing list, in `.fenolite/board.json`. No model key is new, so 0.2.x reads such a document as it reads any other.
- **Pinned digests.** A test that pins the bytes of a KiCad file built from catalog or authored footprints must be regenerated in the same commit. The samples of the Altium verification kit (`examples/kit/*/design.py`, c0091) name `Fenolite:` ids; the kit holds Altium documents, which do not change, so a recorded kit run stays valid. Task 0.1 lists every digest that moves.
