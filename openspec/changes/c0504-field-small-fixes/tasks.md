# Tasks: c0504-field-small-fixes

Rules for every task:

- The field board is private. Nothing from it (names, nets, designators, coordinates, files) goes into tests,
  fixtures, commits or messages. Test data is authored for Fenolite.
- Each fix is its own task with its own proof. Run each touched test file alone with `-n 0`.
- F45 is dropped: it does not reproduce on dev (proposal, "Dropped"). No task.

## 1. F47 degree signs

- [x] 1.1 Reproduce on dev with an authored design: descriptions `-40 °C to 125 °C` and `-40 ℃` through a binary
  and an ASCII build, `schlib.component_record`, and an edit `set_property`. Record each path's outcome as the test's
  starting point (design D3). Change no path that already passes.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/test_text_forms.py -k degree -q -n 0`
- [x] 1.2 `ascii.fold`; the fold in `text_problem(form="binary")` and in `record_bytes`, with no `?`;
  `COMPONENTDESCRIPTION` in the binary form; `altium.text-folded`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/test_text_forms.py tests/unit/backends/altium/test_ascii.py tests/unit/backends/altium/test_binary.py tests/unit/backends/altium/test_schlib.py -q -n 0`
- [x] 1.3 The fold in `edit/records._encode`; `ops.set_property` turns a `RecordError` into `Refused`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_ops.py -k code_page -q -n 0`

## 2. F46 inherited integrity findings

- [x] 2.1 A key per finding in `edit/integrity.py` (`check_document_keyed`), the keyed comparison in
  `session.verify`, `altium.edit.integrity-inherited`, and the hint of `subpoly-gap` (design D2).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_commit.py tests/unit/backends/altium/edit/test_integrity.py tests/unit/backends/altium/edit/test_stage.py -q -n 0`

## 3. F33 drop a stale pour

- [x] 3.1 `ops.unpour`, called by `set_outline`; gate `unpour` in `OPERATIONS`, `ROWS` and `GATES`; `Session.unpour`
  (design D1).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_unpour_c0504.py tests/unit/backends/altium/edit/test_shapes.py -q -n 0`
- [x] 3.2 `altium.edit.pour-stale` in `verify`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_unpour_c0504.py -k stale -q -n 0`
- [x] 3.3 Part J case `J-unpour` in `docs/evidence/altium-edit.md`, numbered after the last case on dev, naming
  `H-A-EDIT-SHAPE`.
  - Proof: `uv run --extra dev pytest tests/unit/test_altium_verification_docs.py -k part_j -q -n 0`

## 4. F41 tidy findings

- [x] 4.1 `tidy.jog`, `tidy.off-45` and `tidy.collinear` in `tidy/codes.py` and `tidy/style.py`; `collinear` in
  `JOINT_KINDS` (design D4).
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/tidy/test_report.py -q -n 0`
- [x] 4.2 `fenolite tidy --report` and `--compare` on any `BoardFrame` board, through c0495's resolver; a step on a
  non-KiCad board is a usage error.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_tidy_cmd.py -q -n 0`

## 5. Docs and changelog

- [x] 5.1 Explain `altium.edit.pour-stale`, `altium.edit.integrity-inherited`, `altium.text-folded`, `tidy.jog`,
  `tidy.off-45` and `tidy.collinear`; list the tidy codes under "tidy" in `docs/cli-contract.md`.
  - Proof: `uv run --extra dev pytest tests/unit/cli/test_explain_cmd.py -q -n 0`
- [x] 5.2 Teach `Session.unpour`, the new codes and `tidy --report` on a `.PcbDoc` on their agent guide pages.
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [x] 5.3 Regenerate the schemas for the report's `collinear` key.
  - Proof: `uv run python tools/gen_schemas.py --check`
- [x] 5.4 `CHANGELOG.md` under `## [Unreleased]`, and `make check-fast`.
  - Proof: `make check-fast`

## Decisions (maintainer, 2026-11-14)

- Decision (maintainer, 2026-11-14): task 1.1's "before" facts are recorded in a comment of
  `test_text_forms.py`, read from the code at 9d7ef2dfd and confirmed by the first run of the new tests. On dev a
  library description `-40 ℃` was written as `-40 ?` beside its `%UTF8%` twin (no issue), a description with
  `°` was refused in a binary build by the 7-bit check of `lens.altium._library_checks`, and an edit value `℃`
  raised `RecordError` out of `Session.apply` (`FEN-1001`).
- Decision (maintainer, 2026-11-14): `record_bytes` keeps its bytes. Conversions carry Altium text whose
  `%UTF8%` twin holds it exactly (`text_problem(read=True)`), and a fold or a refusal there would change or
  break those documents. The fold is applied by the writers of new text instead: `altsym.library_description`
  (library descriptions), `drawn.Drawing.add` for values that are not carried, and `edit/records._encode`.
  The spec scenario "No fold fits" now names the text check and the build refusal.
- Decision (maintainer, 2026-11-14): a library description is checked in the build's form
  (`_library_checks(..., form)`): Windows-1252 in the binary form, 7-bit in the ASCII form, whose refusal
  names the binary form. A description that does not fit even folded stays as given, so the build refuses it
  with `altium.text-unwritable`. The yardstick example (U+00B1 in a description) now passes that check in the
  binary form and is refused later for its unwritten footprints; `REFUSED` in `test_altium_rta2.py` says so.
- Decision (maintainer, 2026-11-14): `Session.apply` turns a `RecordError` of any operation into
  `altium.edit.assertion`, not only in `set_property`. The `altium.text-folded` warning of an edit travels in
  `State.notes` and joins the receipt.
- Decision (maintainer, 2026-11-14): the stale-pour test reads the edited copper from the read models of the
  source and the result (tracks, arcs, vias, fills, regions, and pads at their centre), not from raw records;
  only polygons that still hold poured primitives in the result are judged.
- Decision (maintainer, 2026-11-14): the key of a `layer-fields` finding is the storage, the region's
  `UNIQUEID` (else its polygon and net indices) and the layer pair; a unique-id finding keys on the storage and
  the id; an index finding on the entry's id and the pad index it names.
- Decision (maintainer, 2026-11-14): `tidy.collinear` does not look for a pad at the joint (a `shortcut:`
  comment in `tidy/style.py`); vias and arc ends are looked for.
- Decision (maintainer, 2026-11-14): `tidy --report` of a board that is not KiCad uses
  `_boardview.load_board` (c0495 landed) and runs without net classes (every net `Default`); `--compare` takes
  any board too. The `collinear` keys are optional in the `tidy` result classes, and the changed
  `fenolite.tidy.v0.json` is re-frozen with `gen_schemas.py --freeze-v0`, as c0497 and c0501 did.
- Decision (maintainer, 2026-11-14): the new Part J case is J40 (after c0497's J39). It is written in the kit
  request only; maintainer runs in VM. `H-A-EDIT-SHAPE` stays `INFERRED`.
