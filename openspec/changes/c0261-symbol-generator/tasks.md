## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`design-dsl`, `cli-contract`, `kicad-library-read`, `altium-schematic-writer`, `design-model`), and record under this task, with the date and the base commit:
  - whether c0259 is archived, and the spellings of its envelope keys, its stable-id function, its data tree layout and the device key that names a pin table; align decision 1 and the scenarios with them;
  - whether c0260 already created `catalog/generate/`;
  - whether c0248's `dsl` → `catalog` edge is in the import-graph test;
  - which open change holds a delta of "Project-authored symbols" or of `write_symbol_library`;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `openspec validate c0261-symbol-generator --strict`; `make check-fast`.

## 1. Model and pin tables

- [ ] 1.1 Add `unit` and `body_style` to `SymbolGraphic`, `PinRow`, `PinVariant` and `PinTable` to `model/library.py`, regenerate the schemas, and describe them in `docs/design-model.md` (scenarios "Old canonical JSON unchanged", "Two bodies" at the model level). Proof: `uv run pytest tests/unit/model/test_library.py -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 1.2 Add `catalog/pins.py` with `parse_pins`, `pins_text` and `read_pins`, and author the test tables under `tests/data/pins/` (each opens with the authored-for-Fenolite line). Scenarios "A pin table is read", "Refused rows", "Round trip", "Hidden power refused" (table). Proof: `uv run pytest tests/unit/catalog/test_pins.py -q`.

## 2. Generator

- [ ] 2.1 Write `docs/formats/library/symbols.md` with the constants `G`, `L`, `A`, the stroke, the default group table and the split defaults, each `INFERRED` and Fenolite-authored, and the 100 mil pin-end convention with its public source registered in `docs/evidence/sources.md`. Proof: `make residue`; `uv run pytest tests/unit -k "sources or facts_page" -q`.
- [ ] 2.2 Add `catalog/generate/symbol.py` with sides, order, gaps, buses and geometry (scenarios "Regulator sides", "Interleaved data pins", "Grid property", "A one-pin edit stays local", "Exposed pad stacked on ground", "Ordering variant"). Register `H-G-SYMBOL-LAYOUT` in `docs/hypotheses.md`. Proof: `uv run pytest tests/unit/catalog/test_symbol_generate.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 2.3 Add the automatic and explicit unit split and the codes `symbol.units-split`, `symbol.bus-split` and `symbol.bus-gap` with their `explain.toml` entries (scenarios "A 120-pin part", "Explicit units win"). Proof: `uv run pytest tests/unit/catalog/test_symbol_generate.py -k unit -q`; `uv run pytest tests/unit/cli/test_explain.py -q`.

## 3. Writers

- [ ] 3.1 Extend `backends/kicad/sym.py`: the writer's unit blocks, `unit_name`, hidden pins, alternates and `extends`, and the reader's unit of a graphic (scenarios "Read back", "Existing libraries unchanged"). Proof: `uv run pytest tests/unit/backends/kicad/test_sym.py -q`; `uv run pytest tests/unit/test_examples.py -q`.
- [ ] 3.2 Add the KiCad oracle `tests/kicad/library/test_symbol_generate_oracle.py` and register `H-K-SYM-UNITS-WRITE` (scenario "Multi-unit library exports"). Proof: `uv run pytest tests/kicad/library/test_symbol_generate_oracle.py -rA` (in CI, `kicad-9` and `kicad-10` jobs).
- [ ] 3.3 Extend `altsym.from_symbol_def` with per-unit graphics and flattening of derived symbols, and register `H-A-SCHLIB-GEN-PARTS` with its kit step (scenario "Generated MCU to SchLib"). Proof: `uv run pytest tests/unit/backends/altium/test_altsym.py tests/unit/backends/altium/test_schlib.py -q`; `uv run pytest tests/kicad/altium/test_schlib_oracle.py -rA` (in CI).

## 4. DSL, devices and CLI

- [ ] 4.1 Extend `dsl/symbol.py` with `unit`, `hidden`, `alternates`, `Symbol.unit`, graphics per unit, `Symbol.derive` and `Symbol.from_pins`, and `Design.add` for derived symbols (scenarios "Dual unit with common supply", "Hidden power refused", "Variant built", "Generated symbol in a design"). Proof: `uv run pytest tests/unit/dsl/test_symbol.py tests/unit/dsl/test_symbol_units.py -q`.
- [ ] 4.2 Generate the symbol of a c0259 device that names a pin table and no symbol, with `Footprint` and `ki_fp_filters` from its package. Proof: `uv run pytest tests/unit/catalog/test_devices.py -k pins -q`.
- [ ] 4.3 Add the action words of `fenolite library` and `fenolite library symbol` (scenarios "Existing form unchanged", "Reserved action", "Plan and write", "Wrong suffix"), and describe both in `docs/cli-contract.md`, "library". Proof: `uv run pytest tests/unit/cli/test_library.py tests/unit/cli/test_library_symbol.py -q`; `uv run pytest tests/consistency -q`.

## 5. Closing

- [ ] 5.1 Docs: `docs/symbols.md` (the pin-table format, the layout rule with pictures from the example, units, variants, hidden and stacked pins, Altium notes), a "Multi-unit and derived symbols" section of `docs/dsl.md`, and links from `docs/index.md`. Proof: `uv run pytest tests/unit -k "docs or facts_page" -q`.
- [ ] 5.2 Example: `examples/symbols/` with the illustrative regulator table, a 120-pin authored table and a script that builds both. Proof: `uv run pytest tests/unit/test_examples.py -k symbols -q`.
- [ ] 5.3 Agent guide: add tested lines to `parts.md` for `Symbol.from_pins`, `Symbol.derive`, `Symbol.pin(unit=...)` and `fenolite library symbol`, then run `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent/test_pages.py -q`.
- [ ] 5.4 Evidence: the hypotheses are registered and the evidence matrix is regenerated. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 5.5 Add the entry to `CHANGELOG.md` under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: the v0.6 guard requires `[Unreleased]` to stay empty while the version is `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 5.6 Run `make check-fast`, publish the batch to its working branch, and confirm the required CI jobs (unit and KiCad) on the exact commit. Proof: `make check-fast`, and the required jobs green on the pushed head.
