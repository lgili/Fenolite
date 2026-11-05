# c0419: library symbols place and hide their fields

## Why

The library growth work (fenolite-library c0390) plotted all 101 generic symbols with `kicad-cli sym export
svg` and found two gaps in `backends.kicad.sym.write_symbol_library`:

- **G-4.** Every symbol writes `Reference` at (0, 2.54 mm), `Value` at (0, 0), `Footprint` at (0, −2.54 mm),
  `Datasheet` at (0, −5.08 mm) and `Description` at (0, 0), all left-justified and shown. So in KiCad the
  reference, value and description of a symbol lie on its body, and Description, Footprint and Datasheet
  are never hidden as KiCad's own libraries hide them. A pins record cannot say where its fields go.
- **G-5.** A `line` graphic is written with its first two points only. The pins record parser accepts a
  line of more points without complaint, so the rest of the line is lost silently: in c0390 the inductor,
  the US resistor, the Schottky, Zener and TVS bars and both MOSFET channels lost all but one segment.
  `library check` did not see it; only the plot did.

## What

- **Model.** `SymbolField(name, at, rotation, justify, hidden)` and `SymbolDef.fields`, one entry per
  standard field (`Reference`, `Value`, `Footprint`, `Datasheet`, `Description`) that the definition places.
  Empty by default and left out of the canonical JSON, so every existing definition keeps its data.
- **Pins records.** `[symbol]` may hold `fields = [{ name, at, rotation, justify, hide }, …]`. The parser
  checks the name, refuses a repeated one, and the canonical writer writes the list back. `symbol_def`
  carries it into `SymbolDef.fields`.
- **Writer.** A standard field with a `SymbolField` is written at its `at` and rotation, with its justify
  (none for centred), and `(hide yes)` when hidden; a `Description` with an empty value is still left
  out, as today. A field without an entry keeps today's position
  and effects, so a definition without `fields` keeps its bytes (symbol-generation, "KiCad symbols with
  units, alternates and derivation").
- **Lines.** A `line` graphic is written as an open polyline of all its points. A two-point line keeps its
  bytes.
- **Oracle.** A library with placed and hidden fields and a three-point line is exported by `kicad-cli sym
  export svg` and saved by `sym upgrade`: the saved file holds each field at its place with its hide flag,
  and the polyline with every point.

## Not in this change

- Default placement computed from the body (would change the bytes of every written symbol, design builds
  included): a library sets `fields` per record instead.
- Reading field positions back from a `.kicad_sym` into `SymbolDef.fields` (`library import` keeps today's
  behaviour), and reading an open polyline of more than two points as a `line` (the reader makes it a closed
  `polygon` today). Both are reader follow-ups.
- Fields of DSL-authored symbols.

## Impact

`src/fenolite/model/library.py`, `src/fenolite/catalog/records.py`, `src/fenolite/backends/kicad/sym.py`;
regenerated schemas and model review inventory; `docs/design-model.md`, `docs/library-records.md`.
fenolite-library: once its pin includes c0419, `symbols_table.py` places the fields of its symbols and drops
its line-splitting workaround.
