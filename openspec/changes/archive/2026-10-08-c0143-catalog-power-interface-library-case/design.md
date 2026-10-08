## Context

Measured on 2026-10-08 with this script (`tests/_flagdesign.py` holds it as a function):

```python
from fenolite.dsl import Design, Net, Part, Power, connect, mm
design = Design("regpower")
design.board(mm(30), mm(20))
j1 = Part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="IN")
u1 = Part("U1", "Fenolite:Linear_Regulator", footprint="Fenolite:SOT223_3_Diodes", value="REG")
design.add(j1, u1)
vin, gnd, vout = Net("VIN"), Net("GND"), Net("VOUT")
connect(vin, j1[1], u1["IN"]); connect(gnd, j1[2], u1["GND"]); connect(vout, u1["OUT"])
design.add(Power(vin, gnd))
j1.place(mm(8), mm(10)); u1.place(mm(20), mm(10))
```

| build | tag `v0.2.1` (`fde27c9f`) | v0.4 base before this change |
|---|---|---|
| KiCad, as written | exit 5, `build.vendor-unsafe-name`, "symbol libraries 'Fenolite' and 'fenolite' differ only in letter case" | the same |
| KiCad, without the `Power` line | exit 0; `check --stages erc.kicad` exit 5, `kicad.erc.power-pin-not-driven` on U1-1 and U1-2 (`kicad-cli` 10.0.6) | the same |
| Altium, as written | not run | exit 0 |

The two names: `symembed.FLAG_LIBRARY = "fenolite"` (c0061, `6692f5fb`) and `library="Fenolite"` of the catalog (`8c600121`); both are ancestors of `v0.2.0`. `lens/build.py::_symbol_libraries` refuses two symbol libraries whose names are equal after `casefold()`. The catalog's symbols reach the build as authored symbols, so `Fenolite` is a library the design authors.

## Decisions

1. **The flag joins the library of the design, the flag library is not renamed.** `symembed.flag_library(libraries)` gives the first library, in sorted order, whose name differs from `fenolite` in letter case only, else `fenolite`. Considered: naming the flag library `Fenolite` for every design. Refused: it moves `lib/fenolite.kicad_sym`, its table row and every flag's lib id in every built design with a power flag, the golden `tests/data/kicad/parity/agree/blink.kicad_sch` and 70 pinned builds; and a rebuild into an existing folder on macOS or Windows keeps the file name of the old case while the table names the new one, which then fails on Linux.
2. **Which libraries count.** The libraries of the placed parts' symbols and the libraries the design authors, placed or not (`generate_schematic(..., other_libraries=...)`): both give a file `lib/<name>.kicad_sym`, so both collide with `lib/fenolite.kicad_sym`. With two such libraries the first in sorted order holds the flag; the two then still collide with each other and the build still says so (`build.vendor-unsafe-name`).
3. **A taken name is `build.reserved-library`.** A design that needs a flag and holds `PWR_FLAG` in the flag library is refused at the symbol's lib id, with the hint to rename the symbol or the library. The existing code fits ("kept for Fenolite's own symbols"), so no code is added; its `explain` text is widened. A design that needs no flag keeps the symbol: it built before, and it still does. The catalog holds no symbol of that name, and `tests/unit/catalog` would have to change for one to appear.
4. **Written to apply on `v0.2.1`.** The fix touches `symembed.py`, `schgen.py`, `sch_netlist.py` and `lens/build.py` in places that are the same at the tag, and its core test (`tests/unit/lens/test_build_flag_library.py`, `tests/_flagdesign.py`, `tests/kicad/check/test_flag_library_erc.py`) uses only helpers of the tag. The Altium test is a file of its own (`test_build_flag_library_altium.py`), because `build_altium(authored_symbols=...)` is not in 0.2.x. The registers, the documentation and this folder need a hand on a backport.
5. **The library file with the flag.** A catalog library is written by `sym.write_symbol_library` while all its symbols are authored; with the flag in it, it is written by the general writer of `symembed.write_symbol_library`. Both are read by KiCad 9 and 10 (the ERC test loads the project). Only designs that were refused before get this file.

## Proof

- `tests/unit/lens/test_build_flag_library.py`: the script builds for targets 9 and 10 with `Fenolite:PWR_FLAG`; the blink keeps `lib/fenolite.kicad_sym` and its files; an authored and a project library of that name hold the flag; a taken name is refused, placed and authored; without a flag the name is free.
- `tests/kicad/check/test_flag_library_erc.py`: KiCad's ERC of the built script has no error and no `power_pin_not_driven`; the control without the `Power` line has two.
- `tests/unit/lens/test_build_bytes_pinned.py` and the goldens pass unchanged: the blink and `board_40parts` are pinned designs with a `Power` interface and no catalog part, so no pin was added.
- `tests/unit/lens/test_build_flag_library_altium.py`: the Altium files of the script do not depend on the flag library.

## Evidence

`INFERRED` for the build (Fenolite's own tests); `ORACLE-VERIFIED(kicad-cli)` on 10.0.6 for "KiCad reads the flag in the catalog's library and takes the supply as driven". Not run on the pinned 9.0.9 image in this change (task 3.2).
