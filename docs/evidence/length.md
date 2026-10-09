# Net lengths in KiCad: measurements (change c0106)

What `kicad-cli` counts as the length of a net, measured for change c0106. The facts are in
`docs/formats/kicad/length.md`; the hypotheses are `H-K-NETLEN-TOTAL`, `H-K-NETLEN-VIA10`,
`H-K-NETLEN-VIA9`, `H-K-NETLEN-STACKUP`, `H-K-NETLEN-RULES` and `H-K-NETLEN-MEANDER` in
`docs/hypotheses.md`.

## How it was measured

- Benches: `tests/_lengthbench.py`. Boards built through the model and written by `write_board` for the
  running major, with a `{}` project file unless said. Tracks of 0.25 mm, vias of 0.6 mm, the pads of
  `Mini_R_0603` (0.9 mm × 0.95 mm) and of `Mini_LED_THT_3mm`. Every part, net and thickness is authored
  for the benches.
- KiCad prints a length only as the `actual` of a `length_out_of_range` violation. Each case runs
  `kicad-cli pcb drc --format json --severity-all` twice, with one rule per net,
  `(constraint length (max T − 1 µm))` and `(constraint length (max T + 1 µm))`, `T` being the net's
  total in `length_facts` for the running major. A probe is `equal` when the first run reports every net
  and the second none. Every rules file holds the canary scoped to its own net (c0071), and a run without
  the canary violation fails.
- Run of 2026-10-08: `kicad-cli` 10.0.6, the macOS application, local. The outcomes are pinned in
  `docs/evidence/kicad/probes/10.0.6.json`, and `tests/kicad/length/test_length_parity.py` and
  `test_meander_oracle.py` assert them.
- Run of 2026-10-08 on 9.0.9: `kicad-cli` 9.0.9 in the pinned image (`kicad/kicad:9.0.9`, by digest),
  local. The eleven `length-*` probes are `equal`, as on 10.0.6, and are pinned in
  `docs/evidence/kicad/probes/9.0.9.json`; `tests/kicad/length` gives 21 passed inside the image. The
  column "9.0.9, first record" below still holds the values of the proposal's own measurement
  (2026-10-05, the branch of the review), which the totals of `length_facts` for major 9 reproduce in the
  hermetic tests; the canary outcome of 9.0.9 is the probe file.
- CI run 37772583226 on `04ef42a` (2026-10-08): the `kicad-9` job (the pinned 9.0.9 image) and the
  `kicad-10` job (10.0.6) pass `tests/kicad/length` (21 tests on 9.0.9, the stage verdicts of
  `test_rules` among them) and `tests/kicad/test_probe_results.py`; the `kicad-9` job prints the same
  totals as Fenolite's for every net of `four-explicit`, `six`, `eight` and `four-unprojected`. Task 10.3
  of the change raised the hypothesis rows on that run.

## Totals, two layers (`length-total-two`, `-two-stackup`, `-two-noheight`)

`T` in nanometres as `length_facts` gives it for major 10, and the `actual` that 10.0.6 prints with the
rule 1 µm below it. "Stack-up": the same copper with 35 µm, 1230 µm and 35 µm in the file. "No height":
the project sets `use_height_for_length_calcs` to `false`.

| net | what it holds | T, default | 10.0.6 | T, stack-up | 10.0.6 | T, no height | 10.0.6 | 9.0.9, first record (default) |
|---|---|---|---|---|---|---|---|---|
| `L_CC` | pad centre to pad centre | 18 400 000 | 18.4000 | 18 400 000 | 18.4000 | 18 400 000 | 18.4000 | 18.4 |
| `L_EE` | pad edge to pad edge | 17 500 000 | 17.5000 | 17 500 000 | 17.5000 | 17 500 000 | 17.5000 | 17.5 |
| `L_COL` | two collinear segments | 18 400 000 | 18.4000 | 18 400 000 | 18.4000 | 18 400 000 | 18.4000 | 18.4 |
| `L_ARC` | 4.2 mm, a half circle of radius 3 mm, 8.2 mm | 21 824 778 | 21.8248 | 21 824 778 | 21.8248 | 21 824 778 | 21.8248 | 21.8248 |
| `L_PASS` | a track through a pad, ending 0.8 mm beyond its centre | 19 200 000 | 19.2000 | 19 200 000 | 19.2000 | 19 200 000 | 19.2000 | 19.2 |
| `L_BRANCH` | 18.4 mm between two pads, a 5 mm stub to a third | 23 400 000 | 23.4000 | 23 400 000 | 23.4000 | 23 400 000 | 23.4000 | 23.4 |
| `L_DIE` | 18.4 mm, `(die_length 1.5)` on one pad | 19 900 000 | 19.9000 | 19 900 000 | 19.9000 | 19 900 000 | 19.9000 | 19.9 |
| `L_THT` | through-hole pads joined on `F.Cu` | 20 000 000 | 20.0000 | 20 000 000 | 20.0000 | 20 000 000 | 20.0000 | 20 |
| `L_THT2` | 10 mm on `F.Cu` into a through-hole pad, 10 mm on `B.Cu` out of it | 20 000 000 | 20.0000 | 20 000 000 | 20.0000 | 20 000 000 | 20.0000 | 20 |
| `L_VIA2` | 10 mm on `F.Cu`, a through via, 10 mm on `B.Cu` | 21 580 000 | 21.5800 | 21 300 000 | 21.3000 | 20 000 000 | 20.0000 | 21.545 |
| `L_VIAPAD` | a top pad, 9.2 mm, a via, 9.2 mm, the pad of a part on the bottom side | 19 980 000 | 19.9800 | 19 700 000 | 19.7000 | 18 400 000 | 18.4000 | 19.945 |

## Via heights, four layers (`length-via-four`, `-four-explicit`)

Two 10 mm tracks joined by one via, unless said. "Default": the file holds no stack-up (1.6 mm). "Explicit":
`F.Cu` 35 µm, dielectric 110 µm, `In1.Cu` 17.5 µm, dielectric 1230 µm, `In2.Cu` 17.5 µm, dielectric
155 µm, `B.Cu` 35 µm. KiCad prints four decimals, so 20.15375 mm shows as 20.1537.

| net | copper of the net at the via | T, default | 10.0.6 | T, explicit | 10.0.6 | 9.0.9 height, first record (default / explicit, µm) |
|---|---|---|---|---|---|---|
| `V_F_IN1` | `F.Cu`, `In1.Cu` | 20 532 500 | 20.5325 | 20 153 750 | 20.1537 | 0 / 0 |
| `V_F_IN2` | `F.Cu`, `In2.Cu` | 21 047 500 | 21.0475 | 21 401 250 | 21.4013 | 0 / 0 |
| `V_F_B` | `F.Cu`, `B.Cu` | 21 580 000 | 21.5800 | 21 600 000 | 21.6000 | 1545 / 1565 |
| `V_IN1_IN2` | `In1.Cu`, `In2.Cu` | 20 515 000 | 20.5150 | 21 247 500 | 21.2475 | 0 / 0 |
| `V_IN1_B` | `In1.Cu`, `B.Cu` | 21 047 500 | 21.0475 | 21 446 250 | 21.4462 | 0 / 0 |
| `V_BLIND` | `F.Cu`, `In1.Cu` at a blind via between them | 20 532 500 | 20.5325 | 20 153 750 | 20.1537 | 515 / 136.25 |
| `V_F_F` | `F.Cu` only | 20 000 000 | 20.0000 | 20 000 000 | 20.0000 | 0 / 0 |
| `V_THREE` | `F.Cu`, `In1.Cu` (5 mm) and `B.Cu` at one via | 26 580 000 | 26.5800 | 26 600 000 | 26.6000 | 1545 / 1565 |
| `V_SERIES` | three 10 mm tracks on `F.Cu`, `In1.Cu`, `B.Cu`, two vias | 31 580 000 | 31.5800 | 31 600 000 | 31.6000 | 0 / 0 |
| `VIP` | a via in each end pad, 18.4 mm on `In1.Cu` | 19 465 000 | 19.4650 | 18 707 500 | 18.7075 | — / 0 |
| `DOGBONE` | 1 mm `F.Cu`, a via, 16.4 mm `In1.Cu`, a via, 1 mm `F.Cu` | 19 465 000 | 19.4650 | 18 707 500 | 18.7075 | — / 0 |
| `VIP_BOT` | 18.4 mm on `F.Cu` to a via in the pad of a part on the bottom side | 19 980 000 | 19.9800 | 20 000 000 | 20.0000 | — / 1565 |
| `V_ZONE` | 10 mm on `F.Cu` to a via whose `In2.Cu` copper is a stored zone fill | 10 000 000 | 10.0000 | 10 000 000 | 10.0000 | — / 0 |

## The default stack-up on six and eight layers (`length-via-six`, `-eight`)

Boards without a stack-up, 1.6 mm; two 10 mm tracks joined by one via. The default gives dielectrics of
0.274 mm (six layers) and 1.3 mm / 7 = 0.185714… mm (eight layers).

| net | copper of the net at the via | T, six | 10.0.6 | T, eight | 10.0.6 |
|---|---|---|---|---|---|
| `M_F_IN1` | `F.Cu`, `In1.Cu` | 20 326 500 | 20.3265 | 20 238 214 | 20.2382 |
| `M_F_B` | `F.Cu`, `B.Cu` | 21 580 000 | 21.5800 | 21 580 000 | 21.5800 |
| `M_INNER` | `In2.Cu`, `In3.Cu` | 20 309 000 | 20.3090 | 20 220 714 | 20.2207 |
| `M_IN1_LAST` | `In1.Cu` and the last inner layer | 20 927 000 | 20.9270 | 21 103 572 | 21.1036 |
| `M_BLIND` | `F.Cu`, `In2.Cu` at a blind via between them | 20 635 500 | 20.6355 | 20 458 929 | 20.4589 |

## A stack-up node that is not read (`length-via-four-unprojected`)

The four-layer bench with the explicit stack-up, whose node lost its silkscreen and paste rows. The reader
projects no stack-up from such a node (`kicad.board.stackup-unused`), because KiCad's job file ignores it
(`H-K-STACKUP-COMPLETE`). For lengths 10.0.6 does not ignore it: with the rules built from the totals of
the explicit stack-up the probe is `equal` (`V_F_B` 21.6000, `V_F_IN2` 21.4013, `V_IN1_IN2` 21.2475, the
values of the table above), and the totals of the default stack-up are not what it prints. So
`length_facts` claims no depth for such a file: `stackup` is `none` and the via heights count 0. 9.0.9 is
not measured.

## Rules (`H-K-NETLEN-RULES`)

The rules bench: `SK_P` 20 mm and `SK_N` 21 mm; `BUS0` 20 mm, `BUS1` 21 mm, `BUS2` 23 mm; `SHORT` and
`OPTONLY` 2.4 mm between two pads; `NOTRK` two pads and no copper. What 10.0.6 reports:

| rule | violations |
|---|---|
| `skew (max 0.1mm) (within_diff_pairs)`, `A.inDiffPair('SK')` | one, on `SK_P`: "max skew 0.1000 mm; actual -1.0000 mm; target net length 21.0000 mm (from SK_N); actual 20.0000 mm" |
| `skew (max 0.1mm)`, `A.NetName == 'BUS*'` | `BUS0`: "actual -3.0000 mm; target net length 23.0000 mm (from BUS2); actual 20.0000 mm"; `BUS1`: "actual -2.0000 mm; … actual 21.0000 mm"; none on `BUS2` |
| `length (min 5mm) (max 50mm)` on `SHORT` and `NOTRK` | `SHORT`: "min length 5.0000 mm; actual 2.4000 mm"; `NOTRK`: "min length 5.0000 mm; actual 0.0000 mm" |
| `length (opt 5mm)` on `OPTONLY` | none |
| `length (opt 5mm) (max 50mm)` on `OPTONLY` | none |

The stage `length.rules` is not written yet (it needs the rule kinds of change c0104), so no
`length-rules-*` probe is registered; `test_length_parity.py -k rules` asserts the nets above.

## Meanders (`length-meander-axis`, `-angle`, `-pair`)

The design scripts of `tests/_meanderdesign.py`, built by `fenolite build` for the running major. Each
board carries the canary and the two length rules around the target of its meandered net.

| case | what is built | target (nm) | Fenolite's total (nm) | 10.0.6 |
|---|---|---|---|---|
| `axis` | a 20 mm track along an axis, amplitude 1 mm, pitch 1 mm | 23 000 000 | 23 000 000 | equal |
| `angle` | a 20 mm segment at 30° and a 1.88 mm one, amplitude 1 mm, pitch 1 mm | 25 000 000 | 25 000 000 | equal |
| `pair` | four layers: `USB_P` 26 mm through two vias `F.Cu`–`In1.Cu` (default stack-up), `USB_N` 24 mm meandered with `match`; a skew rule of 1 µm within the pair | 27 065 000 | 27 065 000 | equal |

`equal`: KiCad reports the net with the rule 1 µm below the target, not with the rule 1 µm above, the
board holds no violation type more often than the same design built without the meander, and the pair has
no skew violation.
