# Tasks: c0504-field-small-fixes

Rules for every task:

- The field board is private. Nothing from it (names, nets, designators, coordinates, files) goes into tests,
  fixtures, commits or messages. Test data is authored for Fenolite.
- Each fix is its own task with its own proof. Run each touched test file alone with `-n 0`.
- F45 is dropped: it does not reproduce on dev (proposal, "Dropped"). No task.

## 1. F47 degree signs

- [ ] 1.1 Reproduce on dev with an authored design: descriptions `-40 °C to 125 °C` and `-40 ℃` through a binary
  and an ASCII build, `schlib.component_record`, and an edit `set_property`. Record each path's outcome as the test's
  starting point (design D3). Change no path that already passes.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/test_text_forms.py -k degree -q -n 0`
- [ ] 1.2 `ascii.fold`; the fold in `text_problem(form="binary")` and in `record_bytes`, with no `?`;
  `COMPONENTDESCRIPTION` in the binary form; `altium.text-folded`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/test_text_forms.py tests/unit/backends/altium/test_ascii.py tests/unit/backends/altium/test_binary.py tests/unit/backends/altium/test_schlib.py -q -n 0`
- [ ] 1.3 The fold in `edit/records._encode`; `ops.set_property` turns a `RecordError` into `Refused`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_ops.py -k code_page -q -n 0`

## 2. F46 inherited integrity findings

- [ ] 2.1 A key per finding in `edit/integrity.py` (`check_document_keyed`), the keyed comparison in
  `session.verify`, `altium.edit.integrity-inherited`, and the hint of `subpoly-gap` (design D2).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_commit.py tests/unit/backends/altium/edit/test_integrity.py tests/unit/backends/altium/edit/test_stage.py -q -n 0`

## 3. F33 drop a stale pour

- [ ] 3.1 `ops.unpour`, called by `set_outline`; gate `unpour` in `OPERATIONS`, `ROWS` and `GATES`; `Session.unpour`
  (design D1).
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_unpour_c0504.py tests/unit/backends/altium/edit/test_shapes.py -q -n 0`
- [ ] 3.2 `altium.edit.pour-stale` in `verify`.
  - Proof: `uv run --extra dev pytest tests/unit/backends/altium/edit/test_unpour_c0504.py -k stale -q -n 0`
- [ ] 3.3 Part J case `J-unpour` in `docs/evidence/altium-edit.md`, numbered after the last case on dev, naming
  `H-A-EDIT-SHAPE`.
  - Proof: `uv run --extra dev pytest tests/unit/test_altium_verification_docs.py -k part_j -q -n 0`

## 4. F41 tidy findings

- [ ] 4.1 `tidy.jog`, `tidy.off-45` and `tidy.collinear` in `tidy/codes.py` and `tidy/style.py`; `collinear` in
  `JOINT_KINDS` (design D4).
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/tidy/test_report.py -q -n 0`
- [ ] 4.2 `fenolite tidy --report` and `--compare` on any `BoardFrame` board, through c0495's resolver; a step on a
  non-KiCad board is a usage error.
  - Proof: `uv run --extra geo --extra dev pytest tests/unit/cli/test_tidy_cmd.py -q -n 0`

## 5. Docs and changelog

- [ ] 5.1 Explain `altium.edit.pour-stale`, `altium.edit.integrity-inherited`, `altium.text-folded`, `tidy.jog`,
  `tidy.off-45` and `tidy.collinear`; list the tidy codes under "tidy" in `docs/cli-contract.md`.
  - Proof: `uv run --extra dev pytest tests/unit/cli/test_explain_cmd.py -q -n 0`
- [ ] 5.2 Teach `Session.unpour`, the new codes and `tidy --report` on a `.PcbDoc` on their agent guide pages.
  - Proof: `uv run --extra dev pytest tests/unit/agent/test_pages.py -q -n 0`
- [ ] 5.3 Regenerate the schemas for the report's `collinear` key.
  - Proof: `uv run python tools/gen_schemas.py --check`
- [ ] 5.4 `CHANGELOG.md` under `## [Unreleased]`, and `make check-fast`.
  - Proof: `make check-fast`
