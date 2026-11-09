# Tasks: c0470

## 1. Diagnosis

- [x] 1.1 Census of the public rows `altium-third-party-schdoc-01` to `-17`: count the records per kind, and
  list the kinds that no drawn item maps yet. Proof:
  `uv run pytest tests/corpus/test_altium_drawn_read.py -rA -k census` writes the table into
  `docs/evidence/conversion.md`.
- [x] 1.2 Record the current loss of the Altium → KiCad direction (the KiCad → Altium direction already
  reports its generated schematic as one `changed` row): the `schematic` row and level S between the source and
  the converted drawing, on `blink`, `hier` and the built `examples/altium_hier_board`. Proof:
  `uv run pytest tests/unit/convert/test_schematic_c0470.py -k baseline`.

## 2. Altium extractor (D1)

- [x] 2.1 `backends/altium/drawn_read.py`: symbol poses with part, mirror and display mode, plus wires,
  junctions and net labels. Proof: `uv run pytest tests/unit/backends/altium/test_drawn_read.py -k blink`.
- [x] 2.2 Ports, power ports, sheet symbols and sheet entries, buses and bus entries, no-ERC markers, with
  the port scope of `altium-import`. Proof: the same file, `-k "hier or ports or buses"`.
- [x] 2.3 Typed opaque items: harness records, parameter sets, directives, notes, text frames, graphics and
  images. Proof: the same file, `-k opaque`.
- [x] 2.4 Sheet size, orientation, border and title block. Inexact lengths go to the `altium` bag. Proof:
  the same file, `-k "sheet or inexact"`.
- [x] 2.5 Public rows `-01` to `-17` give no `error` issue. Proof:
  `uv run pytest tests/corpus/test_altium_drawn_read.py -rA`.

## 3. Source symbols (D2)

- [x] 3.1 Altium embedded symbols to KiCad symbols: parts, display modes, pins and decorations. Proof:
  `uv run pytest tests/unit/convert/test_schematic_symbols_c0470.py -k to_kicad`.
- [x] 3.2 `--altium-symbols graphics` is the default for a KiCad source with sheets. Proof: the same file,
  `-k to_altium`.

## 4. Conversion and carriers (D3, D4)

- [x] 4.1 `convert/schematic.py`: `drawing_of` and `write_drawing`, called by `altium_to_kicad.py` and
  `to_altium.py`. A source without sheets keeps `schgen`. Proof:
  `uv run pytest tests/unit/convert/test_schematic_c0470.py -k "writes or board_alone"`.
- [x] 4.2 Carrier `Fenolite.Altium.Sheet` (`fenolite.altium-sheet.v0`) in the title-block `comment 9`,
  written to KiCad and read back; `kicad-cli` 10.0.6 keeps it on a save. Proof: the same file,
  `-k altium_carrier`, and `uv run pytest tests/kicad/test_convert_schematic_oracle.py -k carrier`.
- [x] 4.3 Carrier `Fenolite.KiCad.Sheet` (`fenolite.kicad-sheet.v0`), written to Altium and read back.
  Proof: the same file, `-k kicad_carrier`.
- [x] 4.4 Register both formats in `tools/schema_formats.py` and `schemas/README.md`. Proof:
  `uv run python tools/gen_schemas.py --check` (`schema_formats.py` has no check of its own).

## 5. Report and verification (D5)

- [x] 5.1 Report rows per kind, with reasons in `convert/codes.py`. Proof:
  `uv run pytest tests/unit/convert/test_schematic_c0470.py -k report`.
- [x] 5.2 Level S attributes for part, display mode, port and power style, sheet and title-block fields,
  and typed opaque records. Proof: `uv run pytest tests/unit/checks/equivalence/test_drawn.py -k c0470`.
- [x] 5.3 `convert` runs level S and the drawn netlist check; an unexplained difference exits 5. Proof:
  `uv run pytest tests/unit/convert/test_schematic_c0470.py -k unexplained`.
- [x] 5.4 Round trips Altium → KiCad → Altium on `blink` and the built `examples/altium_hier_board`, the
  drawing of `hier` (no PCB document) through `convert/schematic.py` both ways, and KiCad → Altium → KiCad on the
  public KiCad demo projects: level S finds no difference. Proof:
  `uv run pytest tests/corpus/test_convert_schematic_roundtrip.py -rA`.
  Done 2026-11-08: `blink`, `altium_hier_board`, `hier` and all 32 readable KiCad 10.0.6 demo projects
  (35 passed, 1 skipped `cm5_minima` for its BOM-only symbol, c0334) round-trip with no unexplained
  difference either way and no difference at level S.
- [x] 5.5 KiCad oracle: `kicad-cli` 10.0.6 loads every written sheet. Its netlist equals the source's, and
  its ERC result by type equals the source's. Proof:
  `uv run pytest tests/kicad/test_convert_schematic_oracle.py -rA`.

## 6. Import to Python (D6)

- [x] 6.1 `importer.schematic.drawing_value` extracts the drawing of an Altium source: the import keeps the
  hierarchy and the embedded symbols of the in-memory KiCad conversion, and `import --to python` writes
  `schematic.toml` and `design.load_schematic`. A PCB document alone writes none. Proof:
  `uv run pytest tests/unit/importer/test_altium_drawing_c0470.py -rA`.
- [x] 6.2 The code imported from `blink` and the built `examples/altium_hier_board` builds a KiCad schematic whose drawing equals the source
  drawing of D1 at level S. Proof: `uv run pytest tests/corpus/test_altium_import_python_drawing_c0470.py -rA`.

## 7. Specs and docs

- [x] 7.1 Reconcile `design-conversion` "Altium to KiCad direction" and "Changes of the Altium direction":
  both still name a generated schematic, which now applies only to a source without sheets. Proof:
  `openspec validate c0470-faithful-schematic-conversion --strict`.
- [x] 7.2 `docs/drawn-schematic.md`, `docs/formats/altium/schematic-records.md` and the conversion pages,
  with public sources in `docs/evidence/sources.md`. The agent guide gets a line on the new report kinds.
  Proof: `uv run pytest tests/unit/agent/test_pages.py`.

## 8. Kit

- [x] 8.1 The Altium kit opens the converted sheets of `blink`, `hier` and the KiCad demo projects,
  compiles them, and compares netlist and ERC with the source's: `ALTIUM-VERIFIED(kit)`. Proof: the kit
  report recorded in `docs/evidence/altium-acceptance.md`.

## 9. Closing

- [x] 9.1 Run tests and residue: `make check-fast`, then `ci-complete` on the exact commit.
- [x] 9.2 Update the evidence labels in `docs/evidence/` and the capability pages.
- [x] 9.3 Update `CHANGELOG.md` under `## [Unreleased]`.
