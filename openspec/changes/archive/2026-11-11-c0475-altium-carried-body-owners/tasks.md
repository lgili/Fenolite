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
- [x] 1.3 Rebuild the reported Altium target and read back the reported ownership chains.
  - Proof: local readback of the rebuilt documents.
- [x] 1.4 Add the `CHANGELOG.md` entry and the change docs (`proposal.md`, `design.md`,
      `specs/altium-schematic-writer/spec.md`).
  - Proof: `uv run ruff check . && uv run python tools/gen_agent_guide.py --check`
- [x] 1.5 Compile matched authored reference and regenerated projects in Altium and compare their
      footprint and multiple-name diagnostics and electrical connectivity. This approved scope substitutes
      for the unavailable reported private project.
  - Proof: Altium Designer 24.5.2.23 compiled the two copies (S-2299). Both returned identical named
    net groups and pin exports (34 physical pins and 32 groups), and identical diagnostic files.
    Each has zero footprint and multiple-name diagnostics and the same three errors and two warnings
    from the authored fixture's single-pin GND and floating inputs. Input hashes stayed fixed.
    Comparison SHA-256: `f2a6d3a5ab26b89aa91d221bf7de50384e0488de4c3fdfdb097f86f2b4e76d9e`.
    A negative control reinstated the previous fixed offset on the five footprint and pad-map
    owner references. Altium reported a missing footprint for the affected part, and its pin and
    net exports remained byte-identical to the corrected export. The corrected document has no
    such warning (S-2305). Canary SHA-256:
    `25a4c33058d7ef67c9bbea58914e6e68488dba3b8fe1e02692411097d766f554`.
