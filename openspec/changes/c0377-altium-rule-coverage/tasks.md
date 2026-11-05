## 1. Inventory

- [x] 1.1 Count unmapped kinds and scopes on authored and public documents; rank them.
      Public counts and the reason each form stays open: `docs/formats/altium/rule-file.md`, "Closed
      scope grammar" (S-0580, S-1531). The maintainer's boards were counted outside the repository.

## 2. Mapping

- [x] 2.1 Clearance and Width scopes. Operators in any letter case map (`H-A-RD-PRJ-SCOPE-CASE`,
      INFERRED), and Width, Routing Via Style, Hole Size and Minimum Annular Ring map with either
      `NETSCOPE` (`H-A-RD-PRJ-NETSCOPE-ONE`, INFERRED); the coordinator chose these two classes on
      2026-11-04. The other forms stay declared losses with their reasons (`rule-file.md`).
- [x] 2.2 Plane and polygon connect styles: a declared loss (`no-counterpart`; the board keeps the
      Polygon Connect Style records, c0215). Listed in `rule-file.md`.
- [x] 2.3 Solder mask and paste expansion: a declared loss (`no-counterpart`; the pad expansion modes
      are `INFERRED`). Listed in `rule-file.md`.

## 3. Close

- [x] 3.0 Found on 2026-11-04 (CI 41947475460): the public documents `-04`, `-05` and `-08` map the
      rules the two classes cover; census expectations updated and the via test selects the generic rule by
      its selector (`design.md`). Proof: `FENOLITE_HEAVY=1 FENOLITE_REQUIRE=corpus uv run pytest -n 2 tests/corpus/test_altium_rule_kinds.py
      tests/corpus/test_altium_pour_census.py tests/corpus/test_convert_altium_census.py
      tests/corpus/test_altium_copper.py 'tests/corpus/test_import_corpus.py::test_demo_board_imports_equivalent[18]'`
      (103 passed, 2026-11-05).
- [ ] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
