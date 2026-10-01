# Hypothesis register

Every claim that is not yet verified is a hypothesis with a test or an acceptance-kit request that
settles it. Ids: `H-K-*` (KiCad backend), `H-A-*` (second backend), `H-G-*` (general/model).

| id | backend | statement | level | test or kit request | criterion | result | date |
|---|---|---|---|---|---|---|---|
| H-K-UNIT | kicad | Board and footprint lengths are written in mm with at most 6 decimals, i.e. exact integer nanometres (S-0001) | INFERRED | read every length of the fetched KiCad demo boards at tags 9.0.x and 10.0.x | 100 % of values parse exactly | pending | 2026-09-30 |
| H-A-UNIT | altium | Binary PCB lengths are integers in 1/10 000 mil (S-0002) | INFERRED | decode positions of public corpus boards and compare with `kicad-cli pcb import altium` output | positions agree within 1.27 nm | pending | 2026-09-30 |
| H-G-ANGLE | general | Rotations used by both targets are exactly representable in integer microdegrees | INFERRED | read all rotations in the corpus; non-representable values are kept in `ext` and counted | 0 non-representable values, or each one recorded | pending | 2026-09-30 |
| H-G-ROT-DIR | kicad | A board-file footprint angle θ maps local `(x, y)` to `(x·cosθ + y·sinθ, −x·sinθ + y·cosθ)` in the Y-down file frame (S-0010, S-0019) | KICAD-VERIFIED (10.0.x) | `tests/kicad/test_geometry_frame.py` | front pad differences match at 90° (exact) and 30° (±2 export units) | confirmed with `kicad-cli` 10.0.6 (local, macOS); 9.0.x pending the `kicad-9` job | 2026-10-01 |
| H-G-BOTTOM-PLACE | kicad | For a bottom footprint, absolute = `at + R(θ)·stored`, with no further mirror (S-0019) | KICAD-VERIFIED (10.0.x) | `tests/kicad/test_geometry_frame.py` | back pad differences match at 30° (±2 export units) | confirmed with `kicad-cli` 10.0.6 (local, macOS); 9.0.x pending the `kicad-9` job | 2026-10-01 |
| H-G-BOTTOM-STORE | kicad | The stored children of a bottom footprint equal the library footprint mirrored about local X (S-0019, one footprint of one origin) | INFERRED | board backend change: corpus boards from ≥ 2 origins compared with their library footprints | one rule explains every pad; target CORPUS-VERIFIED | pending | 2026-10-01 |
| H-G-FLIP | kicad | How a library footprint's angle maps to a stored bottom angle (S-0010, S-0019) | INFERRED | same as `H-G-BOTTOM-STORE` | one rule explains every footprint | pending | 2026-10-01 |
| H-G-PAD-ANGLE-ABS | kicad | Pad angles in board files are absolute (the footprint angle included) (S-0019) | INFERRED | same as `H-G-BOTTOM-STORE`; `tests/kicad/test_geometry_frame.py` records the export's `R` field | stored pad angle − footprint angle equals the library pad angle for every pad | pending; observation with `kicad-cli` 10.0.6: pads stored at the footprint angle export `R270` at 90° and `R330` at 30° (front and back) | 2026-10-01 |
| H-G-ARC-ROUND | kicad | KiCad keeps an `fp_arc`'s `mid` and the set `{start, end}` on re-save (S-0001) | KICAD-VERIFIED (10.0.x) | `tests/kicad/test_geometry_arcs.py` | unchanged after `kicad-cli fp upgrade --force` for all four radius/sweep pairs in both orientations | confirmed with `kicad-cli` 10.0.6 (local, macOS); 9.0.x pending the `kicad-9` job | 2026-10-01 |
| H-G-ARC-DIR | kicad | KiCad re-saves graphic arcs with positive `orient2d(start, mid, end)`, swapping `start` and `end` otherwise (observed 10.0.6) | KICAD-VERIFIED (10.0.x) | `tests/kicad/test_geometry_arcs.py` | every re-saved `fp_arc` has positive orientation | confirmed with `kicad-cli` 10.0.6 (local, macOS); 9.0.x pending the `kicad-9` job | 2026-10-01 |
| H-G-PTS-ARC | kicad | `pts` may contain `(arc (start)(mid)(end))` in `fp_poly`, custom-pad `gr_poly` and zone polygons; undocumented in S-0001 (S-0018) | KICAD-VERIFIED (10.0.x) | `tests/kicad/test_geometry_arcs.py`, plus the library scan of the KiCad libraries change | each `pts` arc survives with the same points in the same order | confirmed with `kicad-cli` 10.0.6 (local, macOS); 9.0.x pending the `kicad-9` job; arcs in an `fp_poly`, a custom pad's `gr_poly` and a keepout zone polygon (the last one negatively oriented) kept in order | 2026-10-01 |

Change c0001 (repository bootstrap) added no hypothesis. The first rows (`H-K-UNIT`, `H-A-UNIT`,
`H-G-ANGLE`) came with the design model (change c0004) and stay `INFERRED` until corpus files confirm them.

Change c0002 (CLI contract) adds no hypothesis: `capabilities` and `_echo` read no design format; their
evidence label is `UNVERIFIED` because no external oracle applies to them.

Change c0003 (IP hygiene) adds no hypothesis: it is policy and tooling, verified by its own tests.

Change c0005 (geometry kernel) adds `H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`, `H-G-BOTTOM-STORE`, `H-G-FLIP`,
`H-G-PAD-ANGLE-ABS`, `H-G-ARC-ROUND`, `H-G-ARC-DIR` and `H-G-PTS-ARC`. They state KiCad-frame facts but
use the `H-G-*` prefix because the change's id allocation gives it that prefix; their backend column is
`kicad`.
