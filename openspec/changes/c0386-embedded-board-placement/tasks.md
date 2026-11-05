## 1. Evidence

- [x] 1.1 Ask the altium-rounds-2 session or the maintainer for the Part Q outputs (Q7 to Q12 and phase A)
  and list, per variant, the saved panel and the Altium outputs that exist.
  Done on 2026-11-05 by the Altium rounds agent (S-1592): the list is in `docs/evidence/altium-pcb.md`,
  2026-11-05 Part Q report ("Where the copies lie").
- [x] 1.2 Measure the plain case from the `panel-a` Gerber and drill outputs against `board.PcbDoc`: the
  first copy's corner with Link Location off and the step per column and row. Record the facts with their
  source and label. Proof: an env-gated test reads the outputs and the saved panel.
  Done on 2026-11-05 (S-1592): `FENOLITE_ALTIUM_PANEL_OUTPUTS=<outputs> uv run pytest
  tests/unit/backends/altium/test_panel_placement.py` passes 6 of 6 against the outputs (`panel-a`: 12 of 12
  hits within 0.001 mm); rows in `docs/formats/altium/pcb-document.md`, "Embedded board arrays".
- [x] 1.3 Measure the turned, mirrored and linked variants when their outputs exist; record each, or keep
  the variant `UNKNOWN`.
  Done on 2026-11-05 (S-1592): `ROTATION` 90 turns and `MIRROR` mirrors the whole array about (`X`, `Y`),
  12 of 12 hits each. `panel-link` matches `panel-a` because the fixture board's origin is its shape's corner,
  so Link Location on another board stays `UNKNOWN`; so do other angles, a turn joined with a mirror and the
  mirror's layer side.

## 2. Placement

- [x] 2.1 Read each referenced document relative to the panel document; name a missing or unreadable one.
  - 2026-11-05: `convert.to_kicad.referenced_document` takes `DOCUMENTPATH` relative to the panel document's
    folder (either separator) and reads it with the PCB reader; each array's report item carries a reason
    for a document that reads, is missing, does not read, or is stored as an absolute path (not followed,
    named by its file name only). Every array stays a refused `embedded-board` loss until 2.2. Proof: `uv
    run pytest tests/unit/api/test_conversion_scope.py -q` (13 passed).
- [ ] 2.2 Place the copies of each proved variant with designators and nets kept apart per copy; lift the
  refusal for that variant only. Proof: authored panels plus the env-gated saved panels; KiCad load and DRC
  of the converted board.
  - 2026-11-05: OPEN, waiting on tasks 1.1 to 1.3: no copy placement is recorded from Altium's outputs yet
    (the Part Q phase B run S-1585 is recorded in c0173/c0389, but its outputs are not measured here).

## 3. Close

- [ ] 3.1 Docs (`pcb-document.md`, `conversion.md`), CHANGELOG, `openspec validate --strict`, focused tests,
  `make check-fast`.
