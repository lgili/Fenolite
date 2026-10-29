## Why

A symbol in Fenolite is drawn by hand: `Symbol.pin(..., at=..., length=...)` once per pin, one unit only.
For a 6-pin regulator that is tolerable; for a 144-pin MCU it is a day of error-prone work, and two people
draw the same part two ways. The model already holds what large parts need (`SymbolDef.units`,
`SymbolPin.unit`, `hidden`, `alternates`, `extends`), but neither the DSL nor the KiCad symbol writer can
produce it, and the Altium writer drops alternates.

`docs/research/component-library.md`, section 4.3, proposes that symbols come from **pin tables** through a
**deterministic layout rule**: the facts (pin number, name, electrical type, function group) are data that
a datasheet gives and an agent can extract well (research section 2), and the drawing follows from them.
Section 2 also notes that 54 % of KiCad's library symbols are derived (`extends`), so variants of one
drawing should be one base and thin derived symbols.

## What Changes

- **Pin tables** (`fenolite.pins.v0`, TOML, inside c0259's record envelope): one row per pin with
  `number`, `name`, `type`, optional `group`, `side`, `bus`, `unit`, `shape`, `hidden`, `stacked` (further
  pad numbers of the same pin) and `alternates`; an optional `[symbol]` table (reference prefix, split
  threshold, unit size) and `[[variant]]` rows for derived symbols. Parsed exactly into new model value
  objects `PinTable` and `PinRow`.
- **Layout rule** (`fenolite.catalog.generate.symbol`): supply on top, ground at the bottom, inputs and
  control on the left, outputs and bidirectional pins on the right, buses kept together, a gap between
  groups, every connection point on the 2.54 mm (100 mil) grid, body size from the pin count and an
  authored text-width estimate. Pure, deterministic, integer nanometres.
- **Units.** Explicit `unit` per row, or automatic split above a threshold (default 100 pins): a power
  unit for supply and ground, signal units packed by group and bus in table order, never more than
  `unit_pins` (default 48) per unit.
- **Derived symbols.** `[[variant]]` rows and `Symbol.derive(...)` give `SymbolDef(extends=...)` with only
  their own properties.
- **Writers.**
  - KiCad `write_symbol_library` gains units, per-unit graphics, unit names, hidden pins, stacked pins,
    alternates and `extends`.
  - The Altium SchLib writer (`altsym.from_symbol_def`) gains per-unit graphics and writes derived
    symbols flat. Every generated coordinate is a multiple of 2.54 mm, so the 10-mil grid of the Altium
    writer always holds.
- **Model.** `SymbolGraphic` gains `unit` and `body_style` (default 0, common), so a multi-unit symbol can
  draw one body per unit.
- **DSL.**
  - `Symbol.pin(..., unit=, hidden=, alternates=)`, `Symbol.unit(n, name)`, `Symbol.graphic(..., unit=)`
    and `Symbol.derive(name, ...)`.
  - `Symbol.from_pins(table, *, library)` returns the generated symbol for a parsed pin table.
- **CLI.** `fenolite library symbol PINS.toml --out FILE.kicad_sym|FILE.SchLib` plans the generated
  library (plan and confirm, receipt). This change adds the action words of `fenolite library`, keeping
  the existing `fenolite library BOARD --out|--diff` form.
- **Integration with devices.** A c0259 device record that names a pin table and no symbol gets the
  generated symbol, so `design.part(device=...)` needs no hand-drawn symbol.

## Non-goals

- No body styles (De Morgan alternates of the drawing): body style stays 1, plus 0 for common items.
- No symbol graphics beyond the rectangle body: functional motifs (op-amp triangles, logic gates)
  stay hand-authored, as the catalog's generic symbols are.
- No pin-table extraction from a datasheet (c0265) and no import of third-party symbols (c0264).
- No library checks (c0262 adds `library.pin-grid` and the other symbol rules). This change only
  guarantees that its own output is on grid.
- No change to the 49 hand-drawn catalog symbols.

## Evidence level required

- Parsing and layout: `INFERRED`, unit-tested (`H-G-SYMBOL-LAYOUT`). The layout constants are
  Fenolite-authored and recorded as `INFERRED` in `docs/formats/library/symbols.md`.
- KiCad output: `KICAD-VERIFIED (9.0.x, 10.0.x)` once the oracle reads the generated multi-unit, derived
  and alternate-carrying library (`H-K-SYM-UNITS-WRITE`).
- Altium output: `ORACLE-VERIFIED(kicad-cli)` through the existing SchLib oracle for what KiCad's importer
  reads; `ALTIUM-VERIFIED(kit)` only after the maintainer's kit step (`H-A-SCHLIB-GEN-PARTS`).
- A generated symbol carries the evidence of its pin table; the drawing never raises it.

## Impact

- New: `catalog/pins.py`, `catalog/generate/symbol.py`, `docs/formats/library/symbols.md`,
  `docs/symbols.md`, `examples/symbols/`, tests.
- Changed: `model/library.py` (`PinTable`, `PinRow`, `SymbolGraphic.unit`), `backends/kicad/sym.py`
  (writer and reader of per-unit graphics), `backends/altium/altsym.py`, `dsl/symbol.py`,
  `cli/cmd_library.py`, `cli/data/explain.toml`, `docs/cli-contract.md`, `docs/dsl.md`, the guide page
  `parts.md`, `CHANGELOG.md`.
- Depends on: c0259 (record envelope, stable ids, the data tree and the device's `pins` key) and c0248
  (devices, the `dsl` → `catalog` edge). c0262, c0264 and c0265 build on it.
- Size: about 6 design-days.
