# KiCad geometry conventions

These are the frame, rotation, placement and arc conventions of KiCad board and footprint files, as
used by `fenolite.geometry` (see [../../geometry.md](../../geometry.md)).

- Every fact cites a public source from `docs/evidence/sources.md` and carries an evidence label.
- Facts checked against `kicad-cli` name the hypothesis and the test that checks them.
- The test files are authored for Fenolite (CC0). No KiCad data or source code was copied.

The labels in the table below are those of 2026-10-01:

- `KICAD-VERIFIED (10.0.x)` means the test passed with the local `kicad-cli` 10.0.6. The 9.0.x
  result is added when the `kicad-9` CI job runs the same test.
- `INFERRED` means read from documentation or observed on a single file, not yet checked by a test.

| fact | source | label | hypothesis / test |
|---|---|---|---|
| **Frame.** X to the right, Y down. Board and footprint lengths are written in millimetres, with 1 nm internal resolution. | S-0001, S-0010 | INFERRED (H-K-UNIT pending) | `H-K-UNIT` |
| **Range.** Coordinates are stored as 32-bit integers: about 4 m × 4 m, \|v\| ≤ 2³¹ − 1 nm. Booleans reject values outside this range (`COORD_LIMIT`). | S-0010 | INFERRED | — |
| **Rotation direction.** A footprint angle θ maps local `(x, y)` to `(x·cosθ + y·sinθ, −x·sinθ + y·cosθ)` in the Y-down frame, so positive angles display counter-clockwise, like the R hotkey. | S-0010, S-0019 | KICAD-VERIFIED (10.0.x) | `H-G-ROT-DIR`, `tests/kicad/test_geometry_frame.py` |
| **Bottom-side placement.** The children of a footprint on the back are stored already mirrored. Absolute position = `at + R(θ)·stored`, with no further mirror. | S-0019 | KICAD-VERIFIED (10.0.x) | `H-G-BOTTOM-PLACE`, `tests/kicad/test_geometry_frame.py` |
| **Bottom-side storage.** The stored children equal the library footprint mirrored about local X. Observed on one footprint of one board. | S-0019 | INFERRED | `H-G-BOTTOM-STORE` (board backend change) |
| **Flip rule.** How a library angle maps to a stored bottom angle. The "Flip board items L/R" option chooses the flip axis. | S-0010, S-0019 | INFERRED | `H-G-FLIP` (board backend change) |
| **Pad angles.** Pad angles in board files are absolute (the footprint angle included). Observation: pads stored at the footprint angle export as `R270` at 90° and `R330` at 30°. | S-0019 | INFERRED | `H-G-PAD-ANGLE-ABS` (board backend change) |
| **Three-point arcs.** `gr_arc` and `fp_arc` store `start`, `mid` (a point on the arc) and `end`. | S-0001 | INFERRED | — |
| **Arcs kept on re-save.** A re-save keeps `mid` and the set `{start, end}` of an `fp_arc`. Checked for r = 0.1 mm/10°, 1 mm/1°, 10 mm/0.1° and 50 mm/0.05°, in both orientations. | S-0001 | KICAD-VERIFIED (10.0.x) | `H-G-ARC-ROUND`, `tests/kicad/test_geometry_arcs.py` |
| **Arc direction written.** KiCad writes graphic arcs with positive `orient2d(start, mid, end)` and swaps `start` and `end` otherwise. Consequence: `Arc.orientation` read from a file must not drive any rule. | S-0001 | KICAD-VERIFIED (10.0.x) | `H-G-ARC-DIR`, `tests/kicad/test_geometry_arcs.py` |
| **Circles.** `gr_circle` and `fp_circle` store `center` and `end`, where `end` is a point on the circle. `Circle.from_kicad` keeps the squared radius exact. | S-0001 | INFERRED | — |
| **Arcs inside `pts`.** `pts` may contain `(arc (start)(mid)(end))` in `fp_poly`, custom-pad `gr_poly` primitives and keepout `zone` polygons. S-0001 documents only `xy`. Each such arc survives a re-save with the same three points in the same order, including a negatively oriented one in a zone. | S-0018 | KICAD-VERIFIED (10.0.x) | `H-G-PTS-ARC`, `tests/kicad/test_geometry_arcs.py` |
| **Default approximation error.** The default maximum error when arcs and circles are approximated by segments is 0.005 mm (`DEFAULT_TOL = 5000` nm). | S-0010 | INFERRED | — |
| **IPC-D-356 export frame** (evidence tool only). The header line is `UNITS CUST 0` (0.0001 in = 2540 nm). X = x_file − x₀ and Y = y₀ − y_file: Y up, with one constant origin per file. Tests compare only differences between pads, never absolute positions. | S-0019 | KICAD-VERIFIED (10.0.x) | `tests/kicad/test_geometry_frame.py` (header and differences) |

## Notes

- `tests/kicad/test_geometry_frame.py` exports an authored board with `kicad-cli pcb export ipcd356`.
  - The board holds a front footprint at 90°, a front footprint at 30° and a back footprint at 30°
    with mirrored children.
  - The test converts pad differences to the file frame (`Δx = ΔX·2540`, `Δy = −ΔY·2540` nm) and
    compares them with `Transform.placement`.
  - The comparison is exact at 90°. At 30° it allows ±2 export units per axis, because each exported
    value is quantised once and a difference subtracts two.
- `tests/kicad/test_geometry_arcs.py` re-saves an authored footprint with
  `kicad-cli fp upgrade --force`.
- Both tests run `kicad-cli version` and fail unless the major is 9 or 10. They print the exact
  version.
- When the KiCad backend package `src/fenolite/backends/kicad/` is created (change c0006), its
  `PROVENANCE.md` must carry rows for these facts: rotation direction, bottom-side placement,
  three-point arcs and their direction, and `pts` arcs. Their sources are S-0001, S-0018 and S-0019.
  This change created no backend package.
