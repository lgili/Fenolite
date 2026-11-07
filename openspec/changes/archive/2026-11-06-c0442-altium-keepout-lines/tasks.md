# Tasks: c0442

## 1. Code

- [x] 1.1 `keepout_lines`: marker, parse and the intact guard;
  `uv run pytest tests/unit/backends/altium/test_keepout_lines.py -k marker`.
- [x] 1.2 `convert.altium_to_kicad.keepouts` names the rule areas of a plain stroke;
  `uv run pytest tests/unit/backends/altium/test_keepout_lines.py -k name`.
- [x] 1.3 `lower` writes marked areas of the board and of footprints as Keep-Out layer tracks and arcs;
  `uv run pytest tests/unit/backends/altium/test_keepout_lines.py`.
- [x] 1.4 `equivalent` compares the `form` of two keep-out drawings;
  `uv run pytest tests/unit/backends/altium/test_keepout_lines.py -k equivalent tests/unit/checks/equivalence/test_c0421_pairing.py`.

## 2. Evidence and docs

- [x] 2.1 Round trip of public rows `-01`, `-03`, `-04` and `-06` (S-2010); `pcb-records.md` row,
  `equivalence.md`, CHANGELOG; `uv run pytest tests/unit/test_format_facts.py`.
- [x] 2.2 altium-rounds-2 opens the round trip of row `-01` in Altium Designer: the Keep-Out layer holds
  12 tracks and 8 arcs without the keep-out flag and no keep-out region, and DRC finds no new violation
  against them (kit request).
  Done 2026-11-06 (S-2011): 12 tracks and 8 arcs, no keep-out region, as in the source; the record's
  flag byte stays 0, and Altium reads `IsKeepout` True on each, as on the source's. DRC under the
  document's rules gives 3 729 after Repour All, the same counts as before c0442.
