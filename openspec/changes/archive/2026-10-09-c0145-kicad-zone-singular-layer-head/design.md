## Context

Written, measured and implemented on 2026-10-08 on `v04` at `19ab2ad1` (Fenolite 0.2.1 plus the v0.4 work; "the base" below), then rebased onto `v04` at `775a85d1` (c0104 added), where the checks ran. Local `kicad-cli` 10.0.6 on macOS. Nothing was run on KiCad 9.0.9.

### Measurement 1: which commands refuse, on 0.2.1 and on the base

Boards: `examples/blink_2layer` built by the code under test (format `20260206`, copper rows `F.Cu` and `B.Cu`), with one zone or rule area appended as a token edit. The rule-area boards also hold a plain copper zone on `B.Cu`, so that `fill` has work. The code of the tag `v0.2.1` ran from a scratch worktree of the tag (`PYTHONPATH=<worktree>/src`). Commands: `read_board` then `write_board`; `route --router direct --confirm`; `place --strategy manual --move R1=133mm,109mm --force --confirm`; `fill --confirm`; `build … --out <the folder> --confirm` (a rebuild).

| layer child | on | API | `route` | `place` | `fill` | rebuild |
|---|---|---|---|---|---|---|
| rule area `(layer "*.Cu")` | 0.2.1 | `LossyWriteError` | 7 `FEN-7001` | 7 `FEN-7001` | 1 `FEN-1001` | 7 `FEN-7001` |
| rule area `(layer "*.Cu")` | base | `LossyWriteError` | 7 `FEN-7001` | not run | 1 `FEN-1001` | 7 `FEN-7001` |
| rule area `(layer "*.Cu")` | this change | written | 0 | written (5) | 1 `FEN-1001` | 0 |
| rule area `(layer "F&B.Cu")` | 0.2.1 | `LossyWriteError` | 7 `FEN-7001` | 7 `FEN-7001` | 1 `FEN-1001` | 7 `FEN-7001` |
| rule area `(layer "F&B.Cu")` | this change | written | 0 | written (5) | 1 `FEN-1001` | 0 |
| zone `(layer "*.Cu")` | 0.2.1 | `LossyWriteError` | 7 `FEN-7001` | 7 `FEN-7001` | 1 `FEN-1001` | 7 `FEN-7001` |
| zone `(layer "*.Cu")` | base | `LossyWriteError` | 7 `FEN-7001` | not run | 1 `FEN-1001` | 7 `FEN-7001` |
| zone `(layer "*.Cu")` | this change | written | 0 | written (5) | 1 `FEN-1001` | 0 |
| zone `(layer "F.Cu")` | all three | written | 0 | written (5) | 0 | 0 |
| rule area or zone `(layers "*.Cu")` | all three | written | 0 | written (5) | 0 | 0 |
| rule area `(layers "F&B.Cu")` | all three | written | 0 | written (5) | 0 | 0 |
| zone `(layers "F.Cu")` | all three | written | 0 | written (5) | 0 | 0 |

- The message of every exit 7 is `the write would lose content: field 'layers' cannot be written from the model: (layer "*.Cu") is kept as written` (or `(layer "F&B.Cu")`).
- `place` exits 5 on every board, the controls too: the forced move leaves one placement finding, and the board is written. "not run": on the base before the fix `place` was only run with a move that the command refuses before it writes; the API and the three other commands show the same refusal there.
- `fill` exit 1 is `KicadCliError: kicad-cli zone refill exited 3`: KiCad does not load the board (measurement 3). This change does not alter it.
- The polygon does not matter: the same refusal with points, with an empty `(pts)` and with none was seen when the defect was found.

### Measurement 2: the corpus

Every `.kicad_pcb` of the corpus cache (25 boards: 22 demo rows of the tags 10.0.6 and 9.0.9.1, 3 third-party rows; 22 hold zones), counted by a script over the text: each `(zone …)` up to its `polygon`, its first `layer` or `layers` child.

| head | names | copper zones | rule areas |
|---|---|---|---|
| `layer` | one | 2 228 | 33 |
| `layer` | a wildcard, a mask or several | 0 | 0 |
| `layers` | several plain names | 15 | 10 |
| `layers` | the mask `F&B.Cu` | 1 | 4 |
| `layers` | `*.Cu` | 0 | 0 |
| `layers` | one name | 0 | 0 |

Per file header: `20171130` 19 zones, all `layer` with one name; `20221018` 1 305 and 3 `layers` with names; `20241030` (generator version 8.99, one demo board) the 5 `layers "F&B.Cu"`; `20241229` (9.0) 925 and 19; `20250513` (9.99) 11 and 3; `20260206` (10.0) 1 and 0.

So no board of the corpus holds what this change is about. Where `(layer "*.Cu")` comes from is not known: Fenolite's emitter never writes a wildcard, the repository holds no such text, and no KiCad version in the corpus wrote it.

### Measurement 3: `kicad-cli` 10.0.6

The authored `two_layer.kicad_pcb` with the layer child of its zone and its rule area replaced (probes `pcb-zone-layers-*`, `tests/kicad/board/_zonelayers.py`):

| layer child of both | loads | saved again as |
|---|---|---|
| `(layer "*.Cu")` | no: "Failed to load board: One or more items were found on undefined layers (*.Cu)", `pcb drc` exit 3 | nothing |
| `(layer "F&B.Cu")` | no, the same message with `F&B.Cu` | nothing |
| `(layer "F.Cu" "B.Cu")` | no | nothing |
| `(layers "*.Cu")` | yes | `(layers "F.Cu" "B.Cu")` |
| `(layers "F&B.Cu")` | yes | `(layers "F.Cu" "B.Cu")` |
| `(layers "B.Cu")` | yes | `(layer "B.Cu")` |
| `(layer "B.Cu")` | yes | `(layer "B.Cu")` |

On the `blink` boards of measurement 1, `kicad-cli pcb upgrade --force` printed the load failure and then ended with a segmentation fault (exit 139) for the three singular forms; `pcb drc` ended with exit 3. That is KiCad's, reported outside this change.

Not determined: whether KiCad 9.0.9 loads the singular wildcard; whether any KiCad dialog or any older KiCad version writes it (the corpus says no for the files it holds); which program wrote the board on which `route` first failed.

### The cause

`_Writer.reconcile` (`backends/kicad/pcb.py`) compares each kept child with the node the emitter builds for the same field. It looked that node up by the child's own head. `_emit_zone` writes `layers` for two layers, so for a kept `(layer "*.Cu")` nothing was found, the comparison was "something against nothing", and `_spelling_only` (which knew wildcards only under `layers`) said no: `projection-read-only`. `_key` also compared a `layer` child by its first atom alone, unexpanded.

The same lookup explains two more things seen on 0.2.1: a kept `(layers "B.Cu")` found no `layers` node from the emitter (which writes `layer` for one layer) and was written again from the model; and a kept `(layer "F.Cu" "B.Cu")` whose model was changed to `("F.Cu",)` compared equal by its first atom, so the old child was written for the new value.

## Decisions

1. **One family, in the comparison only.** For the field `layers` of a `Zone` or a `Keepout`, the emitter's node is found under either head (`ZONE_LAYER_HEADS`), and both sides are compared by `_zone_layers_key`: every name, wildcards expanded against the board's copper rows. `_key` is not touched, so no other entity's comparison moves. When the child is kept, both heads are struck from what the emitter would write, so no second layer child can appear.
2. **The file's head is kept, not corrected.** An unchanged `(layer "*.Cu")` goes back into the file although KiCad 10.0.6 refuses it. RT1 is the rule (an unchanged value keeps its fragment), and a writer that repairs what it was not asked to change is a second behaviour. The reader is where a warning would belong (Open question).
3. **A changed layer set over a wildcard is refused under both heads.** That is the written rule for `layers` ("Projected fields on write"; `board.md`, "Projections": a `layers` list with wildcards is read-only). `_spelling_only` now says the same for `layer`. A list of names under `layer` is refused as well when the model changed to another number of layers, by the atom count.
4. **Plain names are written by their number**, as before: `layer` for one, `layers` for several. Measured: KiCad 10.0.6 loads both written forms and saves the same child again.
5. **A declared rule area is not touched.** A rule area of the script (`design.rule_area`, c0103) and any zone the API creates have no kept child, so the family comparison never runs for them: the emitter writes `layers` with every name for an area on all copper of a two-layer board and `layer` for one layer, as on the base. Only a zone that was read keeps the head and the spelling of its file (`tests/unit/lens/test_build_rule_area_layer_head.py`).
6. **No new issue code and no new message.** The existing `projection-read-only` text names the field and the kept child.

## What changes for a board that 0.2.1 could write

- A zone or rule area whose single layer is under `layers`, `(layers "B.Cu")`, written back unchanged: 0.2.1 wrote `(layer "B.Cu")`, now the child is kept. No committed file holds this form, and no pinned build bytes move (a built board has no kept child).
- Nothing else: every other row of measurement 1 that was written is written as before.

## Applying to 0.2.1

The product code is four hunks of `pcb.py` in lines that the tag holds unchanged, and the unit test file is new and uses only helpers the tag has. Tried on 2026-10-08 on a scratch worktree of the tag `v0.2.1` (`fde27c9f`): `git apply --3way` of the diff of `src` and `tests/unit/backends/kicad` applied cleanly ("Applied patch to 'src/fenolite/backends/kicad/pcb.py' cleanly", the test file added); with the tag's code, `tests/unit/backends/kicad/test_pcb_zone_layer_heads.py` gave 52 passed and the tag's whole `tests/unit/backends/kicad` 2 292 passed, 1 skipped. Nothing was committed on the tag and the worktree was removed. The route test and the declared-area test are outside that part and were not tried on the tag (`design.rule_area` is of c0103, which the tag does not hold).

## Open question for the maintainer

1. **Should the reader say that KiCad refuses the board?** A warning `kicad.board.…` on a zone whose `layer` child names several layers would tell the user why `fill` and `check` fail later. It needs an issue code, an explanation and a decision whether it is a warning or an error; not done here.
2. **Should a changed layer set replace a wildcard child?** KiCad itself saves a wildcard as explicit names, so nothing would be lost by writing the model's names over `(layers "*.Cu")`, and it would give a board with `(layer "*.Cu")` a way to become loadable. It moves the answer for the plural head from a refusal to a write; not done here.

## Hypotheses registered by this change

| id | claim | level |
|---|---|---|
| `H-K-ZONE-LAYER-HEAD` | KiCad writes one layer of a zone under `layer` and several under `layers`; 10.0.6 saves a wildcard or a mask under `layers` as explicit names, one name under `layers` as `layer`, and refuses a wildcard, a mask or several names under `layer` | `KICAD-VERIFIED (10.0.x)` |

No source id is added: S-0020 (`kicad-cli` 10.0.6 as an oracle) and S-0058 (the demo boards) carry the facts.

## Risks

- A third-party board with a list of names under `layer` whose model is changed is now refused instead of written with the old child: the old write was wrong.
- The probes are recorded for major 10 only; the `kicad-9` job does not run them.
