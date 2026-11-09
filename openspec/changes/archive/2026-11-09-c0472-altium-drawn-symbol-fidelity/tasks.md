# Tasks: c0472-altium-drawn-symbol-fidelity

- [x] 1.1 Preserve open multi-point symbol lines in `backends.kicad.sym`, `backends.altium.altsym`, and `backends.altium.schdoc` (`RECORD=6` `Polyline` for >2 points), preserve `Comment` field pose over hidden `Value` parameters in `backends.altium.drawn_read._fields`, and preserve `pin_names_hidden` / `pin_numbers_hidden` in `backends.altium.drawn_symbols.component_symbol`, with unit tests and `CHANGELOG.md` entry.
  - Proof: `uv run pytest tests/unit/backends/kicad/test_sym.py tests/unit/backends/altium/test_symbol_graphics.py tests/unit/convert/test_schematic_symbols_c0470.py -q`
  - 2026-11-09: 57 passed in 1.16s.
