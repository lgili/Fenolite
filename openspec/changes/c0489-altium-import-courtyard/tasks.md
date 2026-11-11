# Tasks: c0489-altium-import-courtyard

Rules for every task:

- Public sources only. Each format fact goes in `docs/formats/altium/` with an S- id and an evidence label.
- The maintainer's board is private: codes and counts only. It is never in tests, fixtures, commits or
  messages. Test documents are authored for Fenolite and written by Fenolite's own writer.
- Run each touched test file alone with `-n 0`.

- [ ] 1.1 Look for a public source that states the kind of a mechanical layer (courtyard, assembly) in a PCB
  document; record the key, or record it as `UNKNOWN`, in `docs/formats/altium/pcb-records.md`; record
  `DERIVED_COURTYARD_MARGIN` and `H-A-IMP-COURTYARD` in `docs/formats/altium/import.md`.
  - Proof: `uv run --extra dev pytest tests/unit/test_format_facts.py tests/unit/test_docs_altium_read.py -q -n 0`
- [ ] 1.2 Derive the courtyard on import (`adapter/courtyard.py`, called from `adapter/board.py` and
  `adapter/library.py`) and mark it; tests for "Body larger than the pads" and "A footprint without a body".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_derived_courtyard_c0489.py -q -n 0`
- [ ] 1.3 Give `frame.placed_extents` the derived ring with `source == "derived"`, and add `derived` to
  `PlacedExtent.source`; test for "Two bodies that overlap".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/backends/altium/test_frame.py tests/unit/placement/test_legality.py -q -n 0`
- [ ] 2.1 Skip a derived courtyard in the Altium writer, carry it through KiCad in
  `Fenolite.Altium.DerivedCourtyards`, and skip a matching one on the way back; tests for the two scenarios
  of "A derived courtyard is not written back to Altium".
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_derived_courtyard_c0489.py -q -n 0`
- [ ] 2.2 Run the conversion tests that count footprint drawings and Board6 mechanical layers.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/convert/test_board6_settings_c0464.py tests/unit/convert/test_long_mechanical_c0450.py -q -n 0`
- [ ] 2.3 Regenerate the schemas if `PlacedExtent` or a carrier schema changed.
  - Proof: `uv run python tools/gen_schemas.py --check`
- [ ] 3.1 Add the change to `CHANGELOG.md` under `## [Unreleased]`, and run `make check-fast`.
  - Proof: `make check-fast`
- [ ] 3.2 Maintainer board (private, codes and counts only): after import, every footprint without its own
  courtyard has a derived one; `place` on the imported board reports `place.courtyard-overlap` for parts
  whose bodies overlap; Altium → KiCad → Altium writes no courtyard drawing that the source lacks, and the
  round-trip equivalence still exits 0.
