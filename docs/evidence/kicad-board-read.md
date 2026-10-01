# KiCad board reader: corpus results (change c0009)

Counts from `tests/corpus/test_board_read.py`, `test_board_rt1.py`, `test_board_census.py`,
`tests/kicad/board/test_board_upgraded.py` and `test_board_frame.py`, run on 2026-10-01 with the local
`kicad-cli` 10.0.6 (macOS) and the corpus of `tests/corpus/manifest.toml`; the authored board was also run
in the pinned 9.0.9 image. Only public numbers: manifest ids, head chains and counts, never file content.
Non-heavy items only.

## Boards read

| origin | boards | read with 0 error issues | RT1 (a), (b), (c) | rebuilt boards load on 10.0.6 |
|---|---|---|---|---|
| `kicad-demos` (16 at tag 10.0.6, 5 at 9.0.9.1) | 21 | 21 | 21 | 21 |
| `kicad-demos`, `pcb upgrade --force` copies of the 16 10.0.6 demos | 16 | 16 | 16 | — |
| `third-party`, `pcb upgrade --force` copies (KiCad 5 and 7 files below the read floor) | 3 | 3 | 3 | — |

- The malformed row `kicad-demo-9-0-9-1-pcb-04` raises `FormatError`; the three third-party rows, read
  as published, raise `UnsupportedFormatError` with the `pcb upgrade` hint.
- Content of the 21 native demos: 1 674 footprints, 7 847 pads, 21 499 tracks, 264 track arcs, 2 671 vias,
  71 zones, 12 rule areas, 643 graphics, 585 texts, 2 343 nets.
- `Design.validate()` errors (counted, not asserted): one `model.duplicate-ref` in each of
  `kicad-demo-10-0-6-pcb-08` and `kicad-demo-10-0-6-pcb-11`; 818 `model.single-pin-net` warnings.

## Census

| item | native demos | upgraded third-party copies |
|---|---|---|
| lengths that are not whole nanometres in modelled fields (`H-K-UNIT`) | 0 | 0 |
| angles that are not whole microdegrees in modelled fields (`H-G-ANGLE`) | 0 | 0 |
| atoms with more than 6 decimals (`H-K-SEXPR-NUM-CORPUS`) | 3D model offset `xyz` 2, scale `xyz` 3, pad `roundrect_rratio` 7, dimension text angle 1 | 0 |
| atoms with an exponent | 0 | 0 |
| kept-opaque children | oval drills 108, offset drills 54, `gr_text` layers with `knockout` 124 | oval drills 17 |
| repeated uuids (`H-K-PCB-UUID`) | dimension and its text 13 (6 boards), pads 24 (2 boards), properties 8 (1 board) | zones 1 (1 board) |
| zone outlines kept opaque (`H-K-PCB-ZONE`) | 2 (arcs in `pts`) | 0 |
| headers of the 9.0.9.1 demos (`H-K-TOK-CONSTANTS`) | 5 × `20241229`, `pcbnew`, `9.0` | — |
| `pintype` values | 11 of the 12 electrical types and 8 `<type>+no_connect` forms | 8 types and 4 `+no_connect` forms |

## Exports (`H-K-PCB-POS`)

- `pcb export pos`: every row of the 21 demos and of the authored board matches the model on 10.0.6, and
  the authored board on 9.0.9; bottom rotations are the stored angle modulo 360° (stored −90°, 0°, 90°,
  180° in the demos; 30° in the authored board).
- `pcb export ipcd356` over the 21 demos on 10.0.6: 7 767 pad records matched, 2 671 via records skipped,
  561 truncated keys, 185 ambiguous keys; net partitions equal. The `R` field equals (−stored absolute
  pad angle) mod 360° for every matched pad (`H-G-PAD-ANGLE-ABS`, supporting data).

## Re-save (`H-K-UUID-KEEP`, `H-K-UUID-KEEP-2`)

`pcb upgrade --force` on 10.0.6 keeps the uuid of every item it keeps. In 3 of the 16 demos it drops
uuids: 428 teardrop zones (2 boards), 114 `Footprint` properties (1 board), and 4 `fp_text` items that it
replaces by properties with new uuids (1 board).
