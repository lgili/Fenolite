## 1. Qualification

- [x] 1.1 Accept whole-microdegree parent poses with a bounded fixed-point turn that refuses an unsettled
  test, and `(clearance convexhull)` custom pads. Proof:
  `uv run pytest tests/unit/backends/kicad/test_derived_teardrops.py -q`.
  2026-11-05: done. 85 passed.
- [x] 1.2 Add custom-pad primitive bodies known from inside (line strokes, filled circles, and filled
  polygons or rectangles under exact poses), none on bottom-side footprints. Proof: the same file.
  2026-11-05: done. 85 passed (primitive, frame, polygon-pose and bottom-side cases).

## 2. Native controls

- [x] 2.1 Authored contact controls for a turned rectangle, turned line primitives and a convex-hull
  anchor agree with KiCad DRC on 9.0.9 and 10.0.6. Proof:
  `uv run pytest tests/kicad/board/test_rotated_custom_parent_oracle.py -q` in the kicad-9 and kicad-10 jobs.
  2026-11-05: done locally: 8 passed on the pinned 9.0.9 image and 8 passed on the macOS 10.0.6 `kicad-cli`;
  the CI jobs confirm on the exact commit.
- [x] 2.2 The strict round trip of `kicad-demo-9-0-9-1-pcb-01` proves its six caches equal with KiCad
  10.0.6. Proof: a dated note in `docs/evidence/fidelity.md` with the derived-cache status and counts.
  2026-11-05: done. Status `equal`, 6 caches against 0, 6 regenerated per side; note in `fidelity.md`.

## 3. Evidence and validation

- [x] 3.1 Record the facts in `docs/formats/kicad/frame.md` with source `S-1740`, update the scope of
  `H-K-DERIVED-TD-PROOF` and add a `CHANGELOG.md` line. Proof:
  `uv run pytest tests/unit/test_format_facts.py tests/unit/test_hypotheses_register.py tests/unit/test_evidence_register.py -q`.
  2026-11-05: done. 70 passed (format facts, hypotheses, evidence registers, inferred hypotheses).
- [ ] 3.2 The coordinator's batch `make check-fast` and the required CI jobs pass on the exact commit.
