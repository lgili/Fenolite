## 0. Entry check

- [x] 0.1 Read `openspec list` and the living specs this change touches (`design-dsl`, `cli-contract`, `kicad-library-read`, `altium-schematic-writer`, `design-model`), and record under this task, with the date and the base commit:
  - whether c0259 is archived, and the spellings of its envelope keys, its stable-id function, its data tree layout and the device key that names a pin table; align decision 1 and the scenarios with them;
  - whether c0260 already created `catalog/generate/`;
  - whether c0248's `dsl` → `catalog` edge is in the import-graph test;
  - which open change holds a delta of "Project-authored symbols" or of `write_symbol_library`;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0261-symbol-generator --strict`; `make check-fast`.

  Entry check, 2026-10-29, base commit 3cabfe5a (`circuits-as-code`):
  - c0259 is not archived and not merged (its branch `cac/c0259-library-data-format` is in progress). Its
    design spells the common header `schema`, `id` (`<namespace>:<name>`), `version`, `summary`, `licence`,
    `evidence`, `sources` (and optional `category`, `origin`, `reviewed_by`, `replaces`, `deprecated`); the
    stable id is `record_uid(kind, id)`; the tree holds `pins/<name>.toml`; a device names its pin table
    with `symbol` (a pins record's id). Decision 1 follows that spelling: the table's name is the name part
    of `id`, and `summary` gives `Description` unless `[symbol].description` is set. This change parses
    only the header keys it needs (`schema`, `id`, `version`, `summary`, `licence`, `evidence`, `sources`,
    `category`); the other header keys, `record_uid` and the tree are c0259's and are refused with
    `FEN-3004` until it lands. c0259's explicit drawing (`[symbol].pins`, `[[symbol.graphic]]`) is also
    c0259's: a table here never holds one.
  - c0260 has not created `catalog/generate/`; this change creates it.
  - c0248's `dsl` → `catalog` edge is not in the import-graph test; this change adds the same one-line
    edge (`Symbol.from_pins` calls the generator), which c0248 adds too.
  - No open change holds a delta of "Project-authored symbols"; c0264's design names
    `write_symbol_library` only as a consumer.
  - The open questions have no maintainer answer yet; the recommended answers of `design.md` are used.

  Proof passed (2026-10-29): `openspec validate c0261-symbol-generator --strict` valid; `make check-fast`
  exit 0 on the pushed tree.

## 1. Model and pin tables

- [x] 1.1 Add `unit` and `body_style` to `SymbolGraphic`, `PinRow`, `PinVariant` and `PinTable` to `model/library.py`, regenerate the schemas, and describe them in `docs/design-model.md` (scenarios "Old canonical JSON unchanged", "Two bodies" at the model level). Proof: `uv run pytest tests/unit/model/test_library.py -q`; `uv run python tools/gen_schemas.py --check`.

  2026-10-29: `SymbolGraphic` gains `unit` and `body_style` (default 0); `PinRow`, `PinVariant` and `PinTable` (with the minimum record header until c0259 lands) are in `model/library.py`; schemas regenerated (`library.json`, `schematic.json`); `docs/design-model.md` updated. The 49 catalog symbols keep the canonical JSON digest measured before the change. Proof passed: `tests/unit/model/test_library.py` 13 passed; `gen_schemas.py --check` clean.

- [x] 1.2 Add `catalog/pins.py` with `parse_pins`, `pins_text` and `read_pins`, and author the test tables under `tests/data/pins/` (each opens with the authored-for-Fenolite line). Scenarios "A pin table is read", "Refused rows", "Round trip", "Hidden power refused" (table). Proof: `uv run pytest tests/unit/catalog/test_pins.py -q`.

  2026-10-29: `catalog/pins.py` (`parse_pins`, `pins_text`, `read_pins`, `PinsSchemaError` with `FEN-3002`); tables `tests/data/pins/example_buck.toml` and `example_dual.toml`, declared in `tests/data/MANIFEST.toml`. Proof passed: `tests/unit/catalog/test_pins.py` 26 passed.

## 2. Generator

- [x] 2.1 Write `docs/formats/library/symbols.md` with the constants `G`, `L`, `A`, the stroke, the default group table and the split defaults, each `INFERRED` and Fenolite-authored, and the 100 mil pin-end convention with its public source registered in `docs/evidence/sources.md`. Proof: `make residue`; `uv run pytest tests/unit -k "sources or facts_page" -q`.

  2026-10-29: `docs/formats/library/symbols.md` holds the constants, the default groups and the split defaults (`INFERRED`, Fenolite-authored) and the 100 mil pin-origin facts of KLC S4.1, added to the existing source row S-0339 (read at the `klc` repository commit `6e8cbad9`). Proof passed: `make residue` 0 hits; `pytest tests/unit -k "sources or facts_page"` 70 passed (the page's fact table is checked by `test_symbols_facts_page`).

- [x] 2.2 Add `catalog/generate/symbol.py` with sides, order, gaps, buses and geometry (scenarios "Regulator sides", "Interleaved data pins", "Grid property", "A one-pin edit stays local", "Exposed pad stacked on ground", "Ordering variant"). Register `H-G-SYMBOL-LAYOUT` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/catalog/test_symbol_generate.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

  2026-10-29: `catalog/generate/symbol.py` (`generate_symbol`, `sides`); `H-G-SYMBOL-LAYOUT` registered. The scenario "A one-pin edit stays local" now says that the pins of each side move together when the body grows (the body stays centred, so the top and bottom sides move in opposite directions). Proof passed: `tests/unit/catalog/test_symbol_generate.py` 17 passed; `tests/unit/test_hypotheses_register.py` 38 passed.

- [x] 2.3 Add the automatic and explicit unit split and the codes `symbol.units-split`, `symbol.bus-split` and `symbol.bus-gap` with their `explain.toml` entries (scenarios "A 120-pin part", "Explicit units win"). Proof: `uv run pytest tests/unit/catalog/test_symbol_generate.py -k unit -q`; `uv run pytest tests/unit/cli/test_explain.py -q`.

  2026-10-29: automatic and explicit units, `ISSUE_CODES` of the generator registered in `cli/explain.py` `TABLES` and explained in `explain.toml`. Proof passed: `test_symbol_generate.py -k unit` passed; the explain test is `tests/unit/cli/test_explain_cmd.py` (no `test_explain.py` exists), 8 passed.

## 3. Writers

- [x] 3.1 Extend `backends/kicad/sym.py`: the writer's unit blocks, `unit_name`, hidden pins, alternates and `extends`, and the reader's unit of a graphic (scenarios "Read back", "Existing libraries unchanged"). Proof: `uv run pytest tests/unit/backends/kicad/test_sym.py -q`; `uv run pytest tests/unit/test_examples.py -q`.

  2026-10-29: `write_symbol_library` writes one sub-symbol per unit and body style, `unit_name`, `(hide yes)`, alternates, the non-standard properties (sorted, hidden) and derived symbols (`extends` and own properties, after the base); the reader keeps the unit and body style of a graphic in a symbol of several units or styles. The catalog library keeps the bytes measured before the change on 9 and 10 (`test_existing_libraries_unchanged`). Proof passed: `tests/unit/backends/kicad/test_sym.py` 27 passed; `tests/unit/test_examples.py` 8 passed; also `tests/unit/lens/test_build_bytes_pinned.py`, `test_build_schematic.py` and `tests/unit/backends/kicad` (3186 passed).

- [ ] 3.2 Add the KiCad oracle `tests/kicad/library/test_symbol_generate_oracle.py` and register `H-K-SYM-UNITS-WRITE` (scenario "Multi-unit library exports"). Proof: `uv run pytest tests/kicad/library/test_symbol_generate_oracle.py -rA` (in CI, `kicad-9` and `kicad-10` jobs).

  Open (2026-10-29): the oracle and the row `H-K-SYM-UNITS-WRITE` are added, and the test passed locally on kicad-cli 10.0.7 (1 passed). The proof asks for the CI jobs `kicad-9` and `kicad-10`; the task is ticked once both are green on the pushed head, and the row then moves to `KICAD-VERIFIED (9.0.x, 10.0.x)`.

- [x] 3.3 Extend `altsym.from_symbol_def` with per-unit graphics and flattening of derived symbols, and register `H-A-SCHLIB-GEN-PARTS` with its kit step (scenario "Generated MCU to SchLib"). Proof: `uv run pytest tests/unit/backends/altium/test_altsym.py tests/unit/backends/altium/test_schlib.py -q`; `uv run pytest tests/kicad/altium/test_schlib_oracle.py -rA` (in CI).

  2026-10-29: `from_symbol_def` draws each graphic on the part of its unit (unit 0 on Part Zero), drops graphics of other body styles, and flattens a derived symbol onto `parents` (`model.library.flatten_symbol`); the living requirement "Symbol graphics in libraries and bodies" is modified by this change's delta; `H-A-SCHLIB-GEN-PARTS` registered with kit step L7 of Part L (`docs/evidence/altium-schematic.md`), pending the maintainer's report. The KiCad example's `DUAL_OPAMP` is now drawn from its graphics, so `test_altium_issues.py` no longer expects `altium.symbol-simplified` (its golden libraries are built with generic bodies and keep their bytes). Proof passed: `test_altsym.py`, `test_schlib.py` (with `test_generated_symbol_to_schlib`) and `tests/kicad/altium/test_schlib_oracle.py` 74 passed (oracle on 10.0.7, local; CI runs it again).

## 4. DSL, devices and CLI

- [x] 4.1 Extend `dsl/symbol.py` with `unit`, `hidden`, `alternates`, `Symbol.unit`, graphics per unit, `Symbol.derive` and `Symbol.from_pins`, and `Design.add` for derived symbols (scenarios "Dual unit with common supply", "Hidden power refused", "Variant built", "Generated symbol in a design"). Proof: `uv run pytest tests/unit/dsl/test_symbol.py tests/unit/dsl/test_symbol_units.py -q`.

  2026-10-29: `Symbol.pin(unit=, hidden=, alternates=)`, `Symbol.unit`, `unit=` on graphics, `Symbol.derive` (`DerivedSymbol`), `Symbol.from_pins` (with `variants` and `issues`), and `Design.add` of a derived symbol after its base; the builds flatten an authored derived symbol for resolution and keep `extends` in the library. The `dsl` → `catalog` edge is added to `tests/unit/test_import_graph.py` and `tests/unit/dsl/test_fields.py`. Proof passed: `tests/unit/dsl/test_symbol.py tests/unit/dsl/test_symbol_units.py` 9 passed.

- [ ] 4.2 Generate the symbol of a c0259 device that names a pin table and no symbol, with `Footprint` and `ki_fp_filters` from its package. Proof: `uv run pytest tests/unit/catalog/test_devices.py -k pins -q`.

  Open (2026-10-29): depends on c0259 (device records, the data tree and the device key that names a pin table) and c0248 (`DeviceDef`, `tests/unit/catalog/test_devices.py`), neither merged into `circuits-as-code`. `generate_symbol(table, library=, footprint=, fp_filters=)` already takes the device's `Footprint` and `ki_fp_filters`.

- [x] 4.3 Add the action words of `fenolite library` and `fenolite library symbol` (scenarios "Existing form unchanged", "Reserved action", "Plan and write", "Wrong suffix"), and describe both in `docs/cli-contract.md`, "library". Proof: `uv run pytest tests/unit/cli/test_library.py tests/unit/cli/test_library_symbol.py -q`; `uv run pytest tests/consistency -q`.

  2026-10-29: `fenolite library` reads an action word first (`symbol` runs; `check`, `review`, `import`, `propose`, `fetch` give `FEN-2001`), and `fenolite library symbol PINS... --out FILE.kicad_sym|FILE.SchLib [--library NAME]` plans one library; `docs/cli-contract.md`, "library", describes both. The existing board tests are `tests/unit/cli/test_library_cmd.py` and `test_library_errors.py` (no `test_library.py` exists), unchanged and passing. Proof passed: those and `tests/unit/cli/test_library_symbol.py` 30 passed; `tests/consistency` 572 passed, 35 skipped.

## 5. Closing

- [x] 5.1 Docs: `docs/symbols.md` (the pin-table format, the layout rule with pictures from the example, units, variants, hidden and stacked pins, Altium notes), a "Multi-unit and derived symbols" section of `docs/dsl.md`, and links from `docs/index.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.

  2026-10-29: `docs/symbols.md` (format, layout rule with the example's drawing, units, variants, hidden and stacked pins, Altium notes), "Multi-unit and derived symbols (c0261)" in `docs/dsl.md`, and a row in `docs/index.md`. Proof passed: `pytest tests/unit -k "docs or facts_page"` 70 passed.

- [x] 5.2 Example: `examples/symbols/` with the illustrative regulator table, a 120-pin authored table and a script that builds both. Proof: `uv run pytest tests/unit/test_examples.py -k symbols -q`.

  2026-10-29: `examples/symbols/` with `pins/EXB6202.toml`, the authored 120-pin `pins/EXM120.toml` and `design.py`, which generates both, places the regulator through its variant and builds the four symbols into `lib/Example.kicad_sym`; declared in `tests/data/MANIFEST.toml` and `examples/README.md`, and classified in `tests/unit/lens/test_altium_rta2.py`. Proof passed: `tests/unit/test_examples.py -k symbols` 1 passed.

- [x] 5.3 Agent guide: add tested lines to `parts.md` for `Symbol.from_pins`, `Symbol.derive`, `Symbol.pin(unit=...)` and `fenolite library symbol`, then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.

  2026-10-29: section "Symbols from pin tables" of `parts.md` with a design block (`Symbol.from_pins`, `derive`, `pin(unit=...)`) and a `fenolite-cmd` line of `fenolite library symbol` (10 412 bytes); generated pages rewritten; the block's KiCad check findings are named in `tests/unit/agent/test_pages_kicad.py`. Proof passed: `tests/unit/agent/test_pages.py` 52 passed. (Locally `test_pages_kicad.py` also fails on the page `board-power`, whose second block has no row; that page is not changed here and that test needs kicad-cli 10, so no CI job runs it.)

- [x] 5.4 Evidence: the hypotheses are registered and the evidence matrix is regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.

  2026-10-29: `H-G-SYMBOL-LAYOUT`, `H-K-SYM-UNITS-WRITE` and `H-A-SCHLIB-GEN-PARTS` are registered; `H-A-SCHLIB-GEN-PARTS` joins `schlib.EVIDENCE`, so the evidence matrix and the Altium graduation snapshot are regenerated. Proof passed: `tests/unit/test_hypotheses_register.py` 38 passed; `gen_evidence_matrix.py --check` clean.

- [ ] 5.5 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.

  Open (2026-10-29): `circuits-as-code` is still at 0.6.0, whose release-record guard requires `[Unreleased]` to stay empty; the entry is added once the branch receives `dev`'s `0.7.0.dev0`.

- [ ] 5.6 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.

  Open (2026-10-29): `make check-fast` passed before the push; ticked when the required CI jobs (unit and KiCad) are green on the pushed head.
