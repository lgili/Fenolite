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
- [x] 2.2 Place the copies of each proved variant with designators and nets kept apart per copy; lift the
  refusal for that variant only. Proof: authored panels plus the env-gated saved panels; KiCad load and DRC
  of the converted board.
  - 2026-11-05: `convert.arrays.array_copies` places the arrays that S-1592 proves (unmirrored, `ROTATION` 0
    or 90, the referenced board's origin within 1 µm of its shape's lower-left corner) and refuses the rest
    with a reason each (mirror, angle, origin, board cut-outs, copper layers the board lacks). Each copy:
    ids derived from the array and the copy, designators `<ref>_B<k>`, nets `B<k>/<name>`, parts in the
    generated sheet `B<k>`; the copy step is shared with the flattened panel (`model.replicate`). Proofs:
    `uv run pytest tests/unit/convert/test_embedded_arrays.py tests/unit/api/test_conversion_scope.py
    tests/unit/panel -q` (the authored 2 x 2 panel's copies lie within 10 nm of Fenolite's flattened panel;
    the turned array by the rule; mirror, 45 and 180 degrees and a moved origin stay refused);
    `FENOLITE_ALTIUM_PANEL_OUTPUTS=<outputs>` with `test_panel_placement.py` beside it: the converted copies
    of `panel-a`, `panel-rot90` and `panel-link` put their 12 drilled holes within 0.001 mm of Altium's drill
    hits (worst 1 nm), `panel-mirror` refused; `uv run pytest tests/kicad/convert/test_a2k_load.py -k
    embedded_array` on KiCad 10.0.6: the converted panel loads and its DRC finds four times the board's
    findings per kind. The saved panels also load in KiCad 10.0.6; their further findings come from the
    panels themselves (Altium's default board shape does not enclose the array, and the panel document's
    width rules apply to the copies). KiCad 9.0.9 was not run locally: CI's KiCad job confirms it.

## 3. Close

- [x] 3.1 Docs (`pcb-document.md`, `conversion.md`), CHANGELOG, `openspec validate --strict`, focused tests,
  `make check-fast`.
  - 2026-11-05: docs, CHANGELOG and spec scenarios written; `openspec validate --strict` passes; ruff, format
    and `pyright src` clean; focused tests 198 passed, 5 skipped (env-gated). Open: `make check-fast`, which
    the coordinator now runs once on the integrated batch (rule of 2026-11-05).
  - Closed on CI 42021800567 (exact head 3675515a, now on dev): `ci-complete` green, the four `kicad-10` shards and the coverage audit included; `make check-fast` is covered by the batch's fast stage per docs/ci.md.
