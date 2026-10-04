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

## Measurements of change c0020 (never gates)

Recorded on 2026-10-03 with kicad-cli 10.0.6 (macOS) through `FENOLITE_CENSUS_OUT`. Counts and head names
only.

### Token census (`H-K-TOK-CENSUS`)

`tests/kicad/test_token_census.py::test_observed_paths`. The 10.0-written set is the `pcb upgrade --force`
copies of the 21 readable non-heavy demos and of the 3 third-party boards, plus the cached native boards
whose header is a 10.0 version; the 9.0-written set is the 18 native demos with header `20241229` and
`generator_version "9.0"`.

| count | value |
|---|---|
| head chains in the 10.0-written set | 544 |
| head chains in the 9.0-written set | 498 |
| suspects (only 10.0 writes them) | 56 |
| matched by a token row | 20 |
| accounted for by an ancestor's 10.0 row (`point`, `footprint-units`, `covering`, `plugging`) | 15 |
| `FLOOR_CHAINS` | 0 |
| `PENDING_CHAINS` | 21 |
| unresolved | 0 |

The 21 pending chains are of two kinds. 13 are floor tokens that the 18 9.0-written demos do not happen
to hold (`dimension` children, `font` `bold` and `italic`, footprint `solder_mask_margin` and
`solder_paste_margin`, zone `locked`, `fill` `radius`, `smoothing` and `island_removal_mode`, and
`filled_polygon` `island`, which has value rows only); each waits for an inventory example that loads on
9.0.9. 8 are under `generated` (`base_line_coupled` and its points, `is_time_domain`, `last_tuning_length`,
`target_delay`, `target_delay_min`, `target_delay_max`): tuning-pattern tokens that 10.0 writes and the
inventory has no row for. `H-K-TOK-CENSUS` stays `INFERRED` until the list is empty. The downgrade refusal
(`FEN-7002`) keeps 10.0-format opaque content away from target 9 meanwhile.

### Edge.Cuts outlines (`H-G-EDGE-EXACT`)

`tests/corpus/test_outline_census.py::test_edge_cuts_chain` and
`tests/kicad/board/test_board_upgraded.py::test_outline_census`. Root graphics on edge layers are chained
by exact endpoint equality with `assemble_rings`; edge items inside footprints are only counted.

| origin | boards | chained into closed rings | `geometry.open-contour` | smallest gap up to 1 µm | larger gap | circles | zero-length pieces | edge items inside footprints |
|---|---|---|---|---|---|---|---|---|
| `kicad-demos` (native) | 21 | 18 | 3 | 1 | 2 | 0 | 0 | 14 |
| `third-party` (upgraded copies) | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |

One demo (`kicad-demo-10-0-6-pcb-01`) has two loose endpoints 33 nm apart, so exact chaining leaves its
outline open where a tolerance of 1 µm would close it. The two other open outlines
(`kicad-demo-10-0-6-pcb-14`, `-16`) have gaps of 2.995 mm and 9.24 mm and hold 5 and 9 edge items inside
footprints, which complete the outline and which this census does not chain. `H-G-EDGE-EXACT` therefore
does not hold for the native demos; it stays `INFERRED` with these gaps, and c0022 decides the tolerance.

### Outline rings (`H-G-PLACE-OUTLINE`)

`tests/corpus/test_outline_corpus.py::test_outlines` (c0022), measured on 2026-10-04 over the 21 readable
non-heavy native demos with `backends.kicad.outline.board_outline`, and compared with `board.has_outline`
of `pcb export stats` on `kicad-cli` 10.0.6. No call raised.

| origin | boards | `source` `model` | `source` `edge` (rings) | approximated (arcs or circles) | `open-contour` | `branching-contour` | `no-edge-content` | `footprint-edges-only` | KiCad `has_outline` with a ring | KiCad `has_outline` without a ring |
|---|---|---|---|---|---|---|---|---|---|---|
| `kicad-demos` (native) | 21 | 0 | 18 (18) | 2 | 3 | 0 | 0 | 0 | 18 | 3 |

KiCad reports an outline for all 21 boards. The three boards without a ring are those of the census
above: one whose loose endpoints are 33 nm apart, and two whose outline is completed by edge items inside
footprints. Their problem is `open-contour`, not `footprint-edges-only`, because they also hold root edge
graphics. So the first two clauses of the criterion hold (a ring or a named problem for every board, no
exception) and the third does not: 3 boards with a closed outline in KiCad have no ring. For those boards
`fenolite place` reports `place.no-outline` and judges only courtyard overlaps. A snapping tolerance and
chaining the edge items of footprints stay open (c0022 design, "Open Questions").

### Read and write throughput

`tests/unit/backends/kicad/test_throughput.py::test_read_write_5mib`: a created two-copper board of
tracks and vias, written for target 10; best of three runs for each time, peaks from `tracemalloc` in a
separate pass. Machine: Apple M4, 16 GB, macOS 26.6 (arm64), CPython 3.13.7.

| measure | value |
|---|---|
| board text | 5 746 690 bytes (5.48 MiB) |
| `read_board` | 4.294 s (1.28 MiB/s) |
| `write_board` | 4.652 s (1.18 MiB/s) |
| peak traced memory, read | 134 849 068 bytes (128.6 MiB) |
| peak traced memory, write | 125 715 004 bytes (119.9 MiB) |

No limit is asserted; the test skips without `FENOLITE_CENSUS_OUT`.
