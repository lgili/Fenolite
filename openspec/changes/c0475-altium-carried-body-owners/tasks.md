# Tasks: c0475-altium-carried-body-owners

- [x] 1.1 Resolve the template owner indexes of a component through the records actually written
      (`drawn.component`: template position → live index map for every written record, `OWNERINDEX`
      resolved through it, `FormatError` for an owner no written record provides), so a carried body
      that replaces the template's own body records with a different number of records keeps the
      footprint chain (45 → 44, 46/48 → 45) on the written indexes.
  - Proof: `uv run pytest tests/unit/backends/altium/test_drawn_altium.py -q`
- [x] 1.2 Add the regression test `test_carried_body_owners_shift_the_footprint_chain`: a part whose
      carried body holds a different number of records than its template body (label 4 and polyline 6 among them) with a
      footprint link; assert the written record 45 names the record 44 and the records 46/48 name the
      record 45.
  - Proof: `uv run pytest tests/unit/backends/altium/test_drawn_altium.py::test_carried_body_owners_shift_the_footprint_chain -q`
- [x] 1.3 Rebuild the reported Altium target and read back its six warned parts: every record 45 names
      record 44, and records 46/48 name record 45.
  - Proof: readback of all six parts' blocks from the locally rebuilt documents.
- [x] 1.4 Add the `CHANGELOG.md` entry and the change docs (`proposal.md`, `design.md`,
      `specs/altium-schematic-writer/spec.md`).
  - Proof: `uv run ruff check . && uv run python tools/gen_agent_guide.py --check`
- [ ] 1.5 Compile the regenerated project in Altium and compare its footprint warnings with the original;
      also compare the multiple-name warnings against the original without changing electrical connectivity.
  - Proof: Altium compiler messages for both projects.
