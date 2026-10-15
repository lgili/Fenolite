## Context

**Where a pin's library offset becomes a sheet point.** Searched on dev 25fe079 for `pin_point`, `turned`, `label_angle`, `.mirror` and `rotation // 1_000_000` under `src/`, `tests/` and `tools/`:

| place | what it does |
|---|---|
| `backends/kicad/schlayout.py`: `turned`, `pin_point`, `label_angle` | the one transform; `pin_point` and `label_angle` call `turned` |
| `schlayout.extent`, `body_box`, `unit_bounds`, `text_box`, cluster rooms | boxes of a placed unit, through `pin_point` and `label_angle` |
| `backends/kicad/schgen.py` | the label of each pin of a generated sheet, at `pin_point` with the angle of `label_angle` |
| `backends/kicad/sch.py`, `_text_anchor` | where the Reference and Value of a created instance go, through `pin_point` |
| `backends/kicad/sch_netlist.py`, `_pins` | the own netlist, the grammar check and the stack evidence of any sheet, read or generated |
| `tests/kicad/check/_erccases.py`, `tests/kicad/schematic/_gencases.py`, `test_stacked_corpus.py`, unit tests | through `pin_point` |

No other copy of the transform exists: the Altium writers place symbols by their own records, and the board frame (`geometry.transform`) is a different fact. So the fix is one function.

**The infra commit of v0.4.** The note "39a36681 may be needed" names no object of this clone; on `origin/v04` the only infra commit near the schematic oracle is 7d8c0d0a ("the oracle runner follows the docker form of `FENOLITE_KICAD_CLI`"). It changes how the probe runner starts `kicad-cli`, not a pin point; the oracle test of this change uses the runner as it is on `dev`, so it is not taken here.

## Measurement (2026-10-08, before any product code)

A scratch script read every `.kicad_sch` of the corpus rows (tags 10.0.6 and 9.0.9.1; 125 read, 7 older than the reader's format) with `sch.read_schematic`, and for each pin of each instance with a mirror computed both points: `R` then `M` (rotate first) and `M` then `R` (mirror first). Each point was looked up among the wire ends, the labels, the no-connect flags and the origins of other symbols (a power symbol's pin is at its origin) of the same sheet.

| frame | instances | rotate first wins | tie | mirror first wins | pin points touched (rotate first / mirror first) |
|---|---|---|---|---|---|
| 90°, `mirror x` | 84 | 62 | 21 | 1 | 161 / 49 |
| 270°, `mirror x` | 104 | 80 | 24 | 0 | 175 / 27 |

- No instance holds `mirror y` with 90° or 270°.
- A tie is an instance whose pins touch as many points in both orders: two-pin parts whose two pins swap places.
- The one instance that leans the other way is a capacitor of `jetson-agx-thor-baseboard/m2.kicad_sch` at (167.64, 100.33): its mirror-first point of pin 2 is shared by the pin of a neighbouring capacitor and a wire end; its rotate-first point (167.64, 105.41) is the origin of a power symbol, which the script counts once.
- The 142 instances lie on 20 sheets of both tags; the 9.0.9.1 sheet `test_xil_95108/carte_test` has a nine-pin connector at 270° with `mirror x` whose nine wire ends are all at the rotate-first points and none at the mirror-first ones.
- The mirror axis was checked the same way at 0° (no mirrored instance stands at 180°): 650 instances; with `mirror x` negating py and `mirror y` negating px the pins touch 1 943 points, with the axes swapped 336.

The fact goes to `docs/formats/kicad/schematic.md` as `CORPUS-VERIFIED` (source S-0058, the corpus rows `kicad-demo-10-0-6-sch-*` and `kicad-demo-9-0-9-1-sch-*`).

## Decisions

1. **Rotate, then mirror.** `turned(x, y, rotation, mirror)` applies the counter-clockwise rotation of the library frame and then negates the turned y (`"x"`) or x (`"y"`). `pin_point` keeps its signature and its sheet flip `(x + px′, y − py′)`; `label_angle` follows through `turned`. An unknown mirror is refused before the rotation, as before.
2. **Evidence follows the instance.** `sch_netlist.frame_evidence(sheets)` gives `FRAME_ORDER_EVIDENCE` (`CORPUS-VERIFIED`, `H-K-SCH-PINFRAME-ORDER`) when an instance is mirrored and turned by 90 or 270 degrees, and `()` otherwise; `evidence_of` and the build envelope combine it as they combine the stack evidence of c0123. A sheet without such an instance keeps its `KICAD-VERIFIED` evidence; one with it says that its pin points rest on the corpus until the oracle test runs.
3. **`PROVED_FRAMES` stays the twelve pairs.** Taking the four mirrored quarter turns out would refuse placements files that work with the fix. The docstring now says where the order comes from.
4. **`H-K-SCH-PINFRAME` keeps its level, with a corrected statement.** Its probes prove the rotation sense (the control with the labels of the 90° frame on an unturned instance leaves pins open) and that a label at the computed point closes every pin; they cannot tell the order or the mirror axis. The statement drops "the mirror applied before the rotation" and points to the new row; the result says why.
5. **An oracle test, not a probe.** `tests/kicad/schematic/test_pin_frame_oracle.py` (`needs_kicad`) builds the sheet of `tests/_pinframe.py`: an authored symbol `Probe:Frame` with three pins that no rotation or mirror maps onto each other, twelve instances `U1` to `U12` in the twelve frames, and one global label per pin. Every pin must be on its label's net in `kicad-cli sch export netlist`; with the labels of the mirror-first order the pins of `U6`, `U8`, `U10` and `U12` must be off their nets and the others on them. A new probe id would make `test_probe_results` fail until both probe files are written by a run that this container cannot make (no `kicad-cli`), so none is added; the probes `sch-pin-frame-*` keep their sheets and outcomes.
6. **The corpus stacked-pin test takes every instance.** `left_out` is removed. Counted without `kicad-cli` with the test's own selection: the candidates of `kicad-demo-10-0-6-sch-017` on 10.0.6 are the same 10 stacks before and after; no other root project gains one, so `PINNED` stays. Over all demo sheets read one by one, one stack is new: pins 1 and 10 of `U19` (a TVS diode at 270° with `mirror x`) on `jetson-agx-thor-baseboard/usb.kicad_sch`, a sheet that `_schcorpus.project_files` does not list for the root project at 10.0.6, so the test does not reach it.

## Pinned builds

No generated layout mirrors a unit: only a placements file does, and none of the 35 pinned designs or goldens has one. `tests/unit/lens/test_build_bytes_pinned.py`: 83 passed with the fix, no pin moved, no file under `tests/data` changed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-SCH-PINFRAME-ORDER | The mirror of a symbol instance acts on the turned symbol: rotate counter-clockwise first, then `mirror x` negates the turned y and `mirror y` the turned x | `tests/kicad/schematic/test_pin_frame_oracle.py` on 9.0.9 and 10.0.6 | every pin of the twelve frames on its label's net; the control off its nets at the four mirrored quarter turns |

`CORPUS-VERIFIED` by the measurement above; it becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` when the oracle test passes on both majors in CI. No id above is in another active change (checked 2026-10-08 by `grep` over `openspec/changes`).

## Spec deltas and archive order

| capability | requirement | delta | written from |
|---|---|---|---|
| `kicad-schematic` | "Pin connection points" | MODIFIED | the living text; no active change holds a delta for it |
| `kicad-oracle` | "Order of mirror and rotation is asked of the netlist export" | ADDED | |
| `kicad-oracle` | "Stacked pins of corpus sheets" | MODIFIED | the text of the active change c0123, which adds it |

Archive after c0123.

## Risks / Trade-offs

- [The oracle disagrees with the corpus] → the four mirrored quarter-turn frames leave `PROVED_FRAMES` and the placements file refuses them, as "Schematic naming facts are probed" requires for a frame that fails; the corpus rows are measured again.
- [A user's placements file with such a pair now draws another sheet] → that sheet was wrong in KiCad (labels off the pins); the changelog says so.
