## 1. Evidence

- [x] 1.1 `docs/evidence/sources.md`: S-2120 (owner-board evidence, generic: pads and designator back on the
  old side after an Altium save, `BODYPROJECTION` unchanged), S-2121 (census of the bottom frame, pad
  rotations and `BODYPROJECTION` in the eight public documents) and S-2122 (Altium's J9 flip against
  Fenolite's, by record). Rows in `pcb-document.md` and the status of `H-A-EDIT-FLIP`. Proof:
  `uv run pytest tests/unit/test_legal_docs.py tests/unit/test_format_facts.py -q`.

## 2. Edit session

- [x] 2.1 `ops.flip` writes `ROTATION` 180 − R, and `move_primitives` turns a flipped pad to 180 − r. Proof:
  `uv run pytest tests/unit/backends/altium/edit/test_flip_frame.py -k frame -q`.
- [x] 2.2 A flipped body toggles `BODYPROJECTION` and keeps `MODEL.3D.ROTZ` and `MODEL.2D.ROTATION`
  relative to the component. Proof:
  `uv run pytest tests/unit/backends/altium/edit/test_flip_frame.py -k body -q`.
- [x] 2.3 The existing flip tests still pass. Proof: `uv run pytest
  tests/unit/backends/altium/edit/test_flip_texts.py tests/unit/backends/altium/edit/test_ops.py -q`.

## 3. Kit

- [x] 3.1 Write `c0453-flip.PcbDoc` (case J9's session with this change) and `c0453-flip-body.PcbDoc` (the
  same with an authored body on `D1`), with their sources, under
  `~/fenolite-altium-checks/claude-2026-11-06/c0453-flip/`. Proof: the files read back with `D1`'s frame
  as in 2.1 and its body as in 2.2.
- [x] 3.2 The VM agent's run (open, save, reopen, read) of the two files and of the c0430 flip as a control,
  recorded as S-2123 with its result. Proof: the agent's report with the side of `D1`'s pads, designator
  and body after the reopen.
  Done 2026-11-06 (S-2123): 4 cases, no dialog; expectations hold after the reopen; the control passes.
- [ ] 3.3 Write a flipped body as Altium's own flip does (S-2123): `BODYPROJECTION=1` with `MODEL.3D.ROTZ`
  and `MODEL.2D.ROTATION` of the top body, not 180/180, so Altium's first save changes no byte of it. Proof:
  `uv run pytest tests/unit/backends/altium/edit/test_flip_frame.py -q -n 0` and the VM reopen of
  `c0453-flip-body.PcbDoc` with its body bytes unchanged.
  Code done 2026-11-06: the flip's body record equals byte for byte that of Altium's save of the earlier
  flip (`c0453-flip-body-saved.PcbDoc`); the VM reopen of `c0453-flip-body2.PcbDoc` is pending
  (`~/fenolite-altium-checks/claude-2026-11-06/c0453-flip-body2/`).

## 4. Close

- [x] 4.1 CHANGELOG, the generators and `tools/model_review.py` with `--check`, `openspec validate --strict`,
  and each touched test file alone with `-n 0`.
