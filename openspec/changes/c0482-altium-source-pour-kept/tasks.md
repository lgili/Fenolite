# Tasks: c0482-altium-source-pour-kept

- [x] 1.1 Carry the pours in a conversion to KiCad (`zonepours`, `altium_to_kicad.pour_zones`,
  `to_kicad._carried_pours`), and write them in the Altium writer (`pcbdoc._carried_pour_records`,
  `PcbDocSpec.kept_pours`), with unit tests.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_altium_kept_pour_c0482.py -q -n 0`
- [x] 1.2 Maintainer board (private, codes and counts only): F2 and F5 pass equivalence with the source,
  and their region records equal the source's except for the polygon index.
  - Result 2026-11-11: F2-eq and F5-eq exit 0 with no `equiv.route-vias` or `equiv.route-stub`; 42 of 42
    region records and their 42 twins are byte-equal.
- [x] 1.3 The F2 project compiles in Altium 24.5 as the source does.
  - Result 2026-11-11: Altium 24.5.2.23 compiles the source, F2 and F5 with "Compile successful, no errors
    found": 262 components and 103 nets each, every net with the same pins.
