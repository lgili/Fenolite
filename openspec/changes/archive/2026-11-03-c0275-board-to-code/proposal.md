## Why

Fenolite reads KiCad and Altium boards, converts and compares them, but nothing writes a `design.py`
from a board (`sync --to-source` writes only `placements.toml`). Research section 4.1 of
`docs/research/board-library.md` asks for that path, so a public board can become Fenolite code, join
the layout lens, be proved equal to its source (c0278) and be published in the separate
`fenolite-library` repository (c0279; maintainer decision of 2026-10-29).

## What Changes

- **`fenolite import PATH --to python --out DIR`** under the mutation protocol (`--dry-run`, then
  `--confirm --plan ID`). `PATH` is a KiCad project, board or schematic, or an Altium project or PCB
  document.
- **One emitter on the model**, the same for both backends. It writes `design.py` (board, outline,
  cut-outs and slots, stack-up, nets, net classes, pairs, rules, zones, rule areas, drawings, parts with
  their placements), one module per sheet under `sheets/`, and the copper in `copper.py` as compact tables
  of keyed tracks, arcs and vias, with each item's source lock flag kept.
- **Vendored `lib/`**: footprints through the existing `fenolite library` derive, symbols through the
  symbol writer, and project library tables beside `design.py`.
- **Provenance**: every emitted `.py` starts with an SPDX line (`--licence`), the upstream copyright,
  `Converted from URL@REVISION by Fenolite VERSION on DATE; modified: format conversion to the Fenolite
  DSL`. `PROVENANCE.json` (`fenolite.import-provenance.v0`) records inputs and their SHA-256, upgrade
  steps, tool versions and findings. Upstream `LICENSE` and `NOTICE` files are copied unchanged.
- **Identity**: explicit refs with c0249 keys (`name=`), a `design.lock`, and keys on every copper item,
  zone and drawing, so builds are stable.
- **Lens adoption**: `--adopt` also writes a copy of the source board in which every footprint carries
  `fenolite.path` and the uuid the build derives, and every keyed item its derived uuid, so a build over
  it matches every footprint by uuid and changes nothing.
- **Old inputs**: a KiCad file below the read floor is upgraded with `kicad-cli` on a temporary copy;
  versions and SHA-256 before and after are recorded. Altium inputs use Fenolite's reader.
- **Self-check**: the emitted code is built in memory and compared with the source by `equivalent`
  levels 1 to 5; an unexplained difference exits 5 and writes nothing. An item the DSL cannot express
  exits 7 unless `--allow-lossy` (then a finding per item, or a verbatim item once c0277 is merged).
- **Small DSL additions** the emitter needs: `track_table`, `arc_table`, `via_table` and a `key=` for
  unnamed zones and rule areas.
- Deterministic: same inputs, flags and `--timestamp` give the same bytes.

## Capabilities

- New: `board-to-code`. Modified (ADDED requirements only): `cli-contract`, `layout-lens`,
  `corpus-policy`.

## Non-goals

- No drawn schematic (c0276); until then the build generates its own and `import.schematic-generated`
  says so. No fidelity levels 5 strict to 8 (c0278). No library repository, licence lists or gallery
  (c0279).
- No third-party board, converted code or upgraded copy in the tool repository: tests use boards authored
  for Fenolite, corpus runs stay in temporary folders.
- No Eagle or EasyEDA input; no network access.

## Evidence level required

- Emitter, tables, keys, provenance: `INFERRED`, unit-tested on authored boards (`H-G-IMPORT-CODE`).
- Upgrade of old files: `KICAD-VERIFIED` on 10.0.x (`H-K-IMPORT-UPGRADE`); adoption: `KICAD-VERIFIED`
  on 9.0.x and 10.0.x (`H-K-IMPORT-ADOPT`); Altium inputs: `INFERRED` on Fenolite-written documents
  (`H-A-IMPORT-CODE`). Corpus measurements: `CORPUS-VERIFIED`, never committed.

## Impact

- New: `src/fenolite/importer/` (`emit/`, `tables.py`, `keys.py`, `provenance.py`, `adopt.py`,
  `upgrade.py`), `cli/cmd_import.py`, `docs/import.md`, `schemas/fenolite.import.v0.json`,
  `examples/import_python/`, authored inputs under `tests/data/import_python/`, tests.
- Changed: `dsl/design.py`, `dsl/intents.py` (tables, keys), `library/derive.py` (model input),
  `docs/cli-contract.md`, `docs/dsl.md`, guide page, residue tests, `CHANGELOG.md`.
- Depends on c0249 (keys, lock). Uses c0277 (verbatim items) and c0276 (drawn schematic) when merged.
  Used by c0278 and c0279.
- Size: about 9 design-days.
