## Context

- **Scope.** Milestone v0.4, the complex-board group (`docs/roadmap.md`, "v0.4: proposals on other branches"), id c0100: `board(copper=n)` for even n from 2 to 8, zones and planes on any inner layer, the rebuild rule, and a six-layer build through fill, DRC and export on both majors. The review of 2026-10-05 found the limit in the code and in no change or roadmap line, and found no test of a four-layer build through fill, DRC and export.
- **What exists** (`origin/dev` at `9aba2dff`, read on 2026-10-07). Every place that fixes the count:

  | # | where | what it does today |
  |---|---|---|
  | 1 | `dsl/design.py:354`, `Design.board` | `copper not in (2, 4)` raises `DslError` ("copper must be 2 or 4, not 6") |
  | 2 | `dsl/design.py:34`, `:447-465`, `:554-555` | `INNER_LAYERS = ("In1.Cu", "In2.Cu")`; `planes=` needs `copper == 4` and one of the two names; `zone(layers=…)` takes inner names only at 4 |
  | 3 | `backends/kicad/layers.py:72`, `:137-141` | `INNER_ROWS` holds `(4, "In1.Cu")` and `(6, "In2.Cu")`; `created_layers(copper: Literal[2, 4])` raises `ValueError` for any other value |
  | 4 | `lens/build.py:541-546`, `:608` | `build_design(…, copper: Literal[2, 4])` feeds `created_layers` |
  | 5 | `cli/cmd_build.py:726`, `:974` | `copper=design.copper  # type: ignore[arg-type]`, for the KiCad build and the in-memory build of the Altium branch |
  | 6 | `lens/preserve.py:685-696` | `layout.copper-mismatch` (error, nothing written) when the board's copper names differ from the built table; hint "rebuild with --discard-layout to create the board on the new stack-up" |
  | 7 | `lens/build.py:145-153` | `build.plane-not-lowered` hint "draw a zone on In1.Cu for the net GND in KiCad" |
  | 8 | `backends/altium/pcbrecords.py:77`, `:83`, `:135-145`; `lens/altium_copper.py:77-81`, `:143-168` | no limit at 6 or 8 since c0085. `MAX_COPPER = 32`; `stack_problem` refuses an odd count, more than 32 layers, more than 16 signal or 16 plane layers. `board_layers` gives `layer_names(copper)` (`F.Cu`, `In1.Cu` …, `B.Cu`) for a board that names no copper layer, and `altium.not-lowered` with `where` `stackup` for a stack that `stack_problem` refuses; `altium.copper-stack` is left for a board whose own copper layers repeat or differ in count from the script's. `COPPER_STACKS` (the 2- and 4-layer lists) now serves the library stacks of `libboard`; `lens.altium_copper.COPPER_COUNTS` is a mapping built from it that nothing else reads; `STACK_HINT` still reads "use design.board(..., copper=2) or copper=4, or give the board its copper layers" |
  | 9 | `tests/_boards.py:223`, `tests/_placed.py:64`, `tests/_coppercheck.py:145`; `tests/unit/backends/kicad/test_pcb_write.py:150-152` | fixtures typed `Literal[2, 4]`; a test asserts that `created_layers(6)` raises |

  The living specs state the same rule: `design-dsl` "Design structure and names", "Board and placements in the DSL" and "Zones in the DSL"; `kicad-file-backend` "Created board header". `altium-build` "Copper in an Altium build" names the layer lists of `copper=2` and `copper=4` and no other; c0085's open deltas on `dev` (`altium-pcb-writer` "Layer stacks of any even count", `altium-build` "Copper issue codes") already cover every even count. The committed sample `tests/data/altium/board6` is a six-layer document built from the model API. The model has no limit (`Board.layers` is a tuple), `read_board` names `In<n>.Cu` for any n, and the copper check, the board frame, fill, export, the DSN writer and the views read the board's own copper list.
- **Measured on 2026-10-05,** on the branch where this proposal was written (`review-roadmap-complex-board`); the measurements were not repeated on `dev` at `9aba2dff`, and the tasks record them again as probes. No file of the repository was changed: the probe process installed the proposed counts in memory. `kicad-cli` 10.0.6 locally (macOS); 9.0.9 in the pinned image `kicad/kicad:9.0.9@sha256:e638b79b…` under `docker run --platform linux/amd64`, in one container.
  1. *Created tables on 10.0.6.* `tests/_boards.py::created_board` with the table of n copper layers, rows `(2k + 2, "In<k>.Cu", signal)` after `F.Cu` for k = 1 … n − 2, written for targets 9 and 10 with a `{}` project file. On a copy: `kicad-cli pcb drc --format json --severity-all -o drc.json b.kicad_pcb`, `kicad-cli pcb export gerbers -o g/ b.kicad_pcb`, `kicad-cli pcb upgrade --force b.kicad_pcb`.

     | n | `pcb drc` | copper Gerbers | rows after `pcb upgrade --force` |
     |---|---|---|---|
     | 2, 4, 6, 8, 10, 16, 32, 34 | exit 0, report written; at every n the same 5 warnings and 3 unconnected items, those of the test board's own content | n | equal (number, name, type) |
     | 3, 5 | exit 3, "Failed to load board: 3 is not a valid layer count" (5 for n = 5) | none (exit 3) | `pcb upgrade` ends with signal 11 |

     Target-9 and target-10 texts gave the same results.
  2. *Created tables on 9.0.9.* The target-9 texts of n = 2, 4, 6, 8, 32 and 34 load (`pcb drc` exit 0, the same warnings) and give n copper Gerbers; n = 3 gives "Failed to load board" (exit 3). `kicad-cli` 9.0.9 has no `pcb upgrade` (`pcb` lists `drc`, `export`, `render`) and no `pcb drc --refill-zones`, as S-0037 says.
  3. *KiCad's own boards* (corpus, S-0058): demo `kicad-demo-10-0-6-pcb-01` (header 20250513) holds `(0 "F.Cu" signal)`, `(4 "In1.Cu" signal)`, `(6 "In2.Cu" signal)`, `(8 "In3.Cu" signal)`, `(10 "In4.Cu" signal)`, `(2 "B.Cu" signal)`; demo `-pcb-13` (header 20241229) adds `(12 "In5.Cu" signal)` and `(14 "In6.Cu" signal)`. No inner row has a user name.
  4. *Builds.* A blink variant with `copper=n`, a zone on every inner layer (GND on `In1.Cu`, `In3.Cu`, `In5.Cu`, VIN on the others), the `LED_A` track stepping through a via to the deepest inner layer and back to `B.Cu`, and one via drop each for GND and VIN; `fenolite build --kicad-version M --seed 1 --timestamp 2026-10-05T00:00:00Z --no-backup --confirm`, then `fill --confirm`, `check`, `export --all --confirm`, then `build` again; n = 4, 6, 8 and M = 9, 10:
     - `build` exit 0, its only issue `model.single-pin-net` (the blink's `VIN`);
     - `fill`: every zone filled, one fill each, no island (2, 4 and 6 zones);
     - `check`: `drc.kicad` ok with 0 violations, 0 unconnected items and the canary fired; `copper.clearance` 0 shorts and 0 clearance findings (31 pairs at 6, 40 at 8); `zone.fill` current; `roundtrip` RT1 tree-equal;
     - `export --all`: one Gerber per copper layer, X2 file functions `Copper,L1,Top` … `Copper,L<n>,Bot`; the job file states `LayerNumber` n, `BoardThickness` 1.6 and n − 1 equal dielectrics (0.274 mm at 6, 0.1857 mm at 8), KiCad's default, since no stack-up is written;
     - the second `build` writes the board with the same bytes. Every step took less than 5 s.
  5. *9.0.9 on the filled target-9 boards* of n = 6 and 8, with their project and rules files: `pcb drc` 0 violations, 0 unconnected items; n copper Gerbers.
  6. *Side cases* (10.0.6):
     - the eight-layer script, and the four-layer one, over the six-layer board: exit 5, `layout.copper-mismatch` ("the board's copper layers ['F.Cu', 'In1.Cu', …] differ from the design's […]"), with the `--discard-layout` hint;
     - a four-layer build whose board gets `(8 "In3.Cu" signal)` and `(10 "In4.Cu" signal)` after `In2.Cu` by token edit, as KiCad's board setup adds layers: rebuilt with the four-layer script, exit 5 `layout.copper-mismatch`; with the six-layer script, exit 0 and `U1`, `R1`, `D1` kept;
     - the six-layer script with `--target altium --dry-run` was refused on that day (`altium.copper-stack`, "only 2 and 4 are"). That refusal no longer exists on `dev` (row 8 of the table): c0085 removed it. The case was not measured again; task 4.2 builds it and the scenarios of "Script layer counts in an Altium build" state the expected result;
     - `planes={"In4.Cu": gnd}` at 6 layers: `build.plane-not-lowered` with the hint "draw a zone on In4.Cu for the net GND in KiCad";
     - `write_dsn` on the six- and eight-layer boards: 6 and 8 layers `(type signal)`, no plane, no issue.
  7. *Row type `power`* on `In3.Cu` of the six-layer table, both texts, 10.0.6: kept by `pcb upgrade --force`; the Gerber X2 file function stays `Copper,L4,Inr`.
- **Constraints.** Stdlib only; integers only; the DSL imports only `model` (`tests/unit/test_import_graph.py`); counts of 2 and 4 keep their bytes.

## Goals / Non-Goals

**Goals:**
- A script declares 2, 4, 6 or 8 copper layers and gets the KiCad table that KiCad itself writes, on both targets.
- Zones, planes and script copper take every inner layer of the count.
- A rebuild keeps the layout of a board of any allowed count, and tells how to rebuild one whose count differs.
- Each allowed count is proved by `kicad-cli` on both majors, through fill, DRC and export.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **The bound is 8, even counts only.** `CREATED_COPPER_COUNTS = (2, 4, 6, 8)`.
   - Even: both majors refuse a table of 3 or 5 copper layers (measurement 1), so an odd count could never be checked.
   - 8: the yardstick of the review asks for 4 to 8, and the changes that build on this one are written against that range (c0101 stack-up, c0105 impedance, c0115 insulation between layers, c0119 the yardstick board). Every allowed count is proved on both majors (Decision 10). Raising the bound later is additive: the constant and probe rows, since both majors load up to 34 (measurements 1 and 2).
   - Rejected: KiCad's own range. Both majors loaded 34 copper layers here, so its upper end is not even known; each count would need a probe, and every dependent change would have to give each one a stack-up and an impedance table.
   - Rejected: any even count without a bound. A count no test exercises would be promised.

2. **One rule for the inner rows.** `inner_rows(copper)` gives `(2k + 2, "In<k>.Cu", "signal", None)` for k = 1 … copper − 2, inserted after `F.Cu` in that order; the other rows stay those of today's two-copper table. The rule reproduces today's rows at 2 and 4 and KiCad's demos at 6 and 8 (measurement 3), and both majors re-save or load it unchanged (measurements 1 and 2). The rows are the same for both targets: 9.0 introduced this numbering (`docs/formats/kicad/board.md`, "9.0 renumbered the layers").
   - Rejected: one literal table per count. Four tables of the same shape, and a fifth to write on every raise.

3. **Two constants, one test.** The DSL may import only `model`, so it cannot read the backend's tuple. `fenolite.dsl.design.COPPER_COUNTS` and `fenolite.backends.kicad.layers.CREATED_COPPER_COUNTS` hold the same four counts, and a unit test asserts that they are equal, as `tests/unit/dsl/test_properties.py` does for the two copies of `RESERVED_PROPERTIES`.
   - Rejected: a constant in `model`. The model holds boards of any count read from files; a count limit there would mislead.
   - Rejected: the DSL importing the backend. It breaks the layering.

4. **Inner layers in the DSL.** `inner_layers(copper)` gives `In1.Cu` … `In<copper − 2>.Cu`; `Design.copper_layers` gives `("F.Cu", *inner_layers(copper), "B.Cu")` for the declared count. `board()` refuses a value that is not an `int` of `COPPER_COUNTS` (a `bool` and a `float` included: `6.0 in (2, 4, 6, 8)` is true in Python), naming the counts. `planes=` takes any inner layer of the count, and `zone(layers=…)` any layer of `Design.copper_layers`; the messages name the allowed layers. `INNER_LAYERS` is removed: `fenolite.dsl` never exported it, no example uses it, and a four-layer tuple would be wrong at 6 and 8.
   - Rejected: keeping `INNER_LAYERS` as the four-layer tuple. A constant that is wrong for two of the four counts invites misuse.

5. **Planes stay unwritten on KiCad; the hint names the script call.** A plane is still a build parameter: on KiCad the layer stays a `signal` row and `build.plane-not-lowered` is given, now with the hint `design.zone(<net>, layers=("<layer>",))` for the net and layer, instead of a step in the KiCad editor (measurement 6). c0038 left lowering open (its Open Question 1).
   - Rejected: a zone over the outline per plane. It needs a name, settings and a rebuild rule for a zone the script did not declare, while one `design.zone()` call gives the same copper.
   - Rejected: the row type `power` for a plane layer. It changes no Gerber (measurement 7), and the layer table of a rebuilt board is the board's own ("Board content outside the design is kept"), so a plane declared after the first build would not reach it. Whether routing needs a plane marker is c0107's question.

6. **The rebuild rule.** A board whose copper names equal those of `created_layers(copper)` keeps its layout at every count, as it does at 2 and 4 (measurement 4, second build; measurement 6, layers added in KiCad). When they differ, `layout.copper-mismatch` stays an error. Its message names the board's copper layers and count and the script's count. When the board holds Fenolite's table of an allowed count m (`layers.created_count(names)`), the hint names `design.board(..., copper=m)`, which keeps the board's layout, and `--discard-layout`, which creates the board on the script's count without it; otherwise only `--discard-layout`. This is the case of a board given more layers in KiCad, which today cannot be rebuilt at all.
   - Rejected: keeping the layout across a change of count. c0102 owns it ("an outline or layer-count change that keeps the routed layout").
   - Rejected: taking the board's count over the script's. The script is the source of the count.

7. **Requirements shared with other changes** (checked on `origin/dev` at `9aba2dff`, `openspec/changes/*/specs`, on 2026-10-07).
   - No open change on `dev` holds a delta of the five requirements this change modifies; each MODIFIED delta here is the living text with this change's edits only. c0069 is archived, and its "Board content outside the design is kept" still holds the copper sentence unchanged: the sentence refers to `layers.created_layers(copper)`, whose domain this change widens, and the new rule is the ADDED "Layer count across rebuilds".
   - "Board and placements in the DSL": c0096 (implemented on its own branch, not on `dev`), this change and c0102 each hold a full MODIFIED text. Order: c0096, c0100, c0102. If c0096 is not on `dev` when this change lands, c0096 regenerates on the text this change leaves (its copy still says "`copper` MUST be 2 or 4"). c0102 always regenerates after both.
   - "Zones in the DSL": this change, then c0102, which regenerates.
   - "Created board header": c0100, then c0101, then c0112; each later one regenerates from the living text. The same order holds for "Modelled board content" and "Projected fields on write", which this change does not touch (c0101, c0103, c0112).
   - "Planes in a build": this change, then c0107, which regenerates.
   - c0102 will modify "Layer count across rebuilds" when a count change keeps the layout; it can only do so once this change is archived, because the requirement is ADDED here.
   - Rejected: stating the new hint inside a MODIFIED "Board content outside the design is kept". c0102 modifies that requirement, and two full texts of it would have to be reconciled for one sentence.

8. **The Altium build needs no new code for the count; the requirement states what c0085 gives.** On `dev` the only refusal of a six-layer script is the DSL guard: `board_layers` returns `layer_names(copper)`, `plane_nets` takes every inner layer of that list, and c0085's writer lays out any even stack up to 32 layers (table row 8). Lifting the guard therefore makes `--target altium` write a six- or eight-layer document. "Script layer counts in an Altium build" states it, with one scenario per count, and rewords `STACK_HINT`, the one place that still names 2 and 4.
   - The names of `layer_names(copper)` are those of `Design.copper_layers`, so a zone, a plane or script copper on `In4.Cu` of the script is on a layer of the document.
   - `lens.altium_copper.COPPER_COUNTS` (a mapping from count to layer list, read by nothing on `dev`) is left as it is. It shares its name with the new tuple `fenolite.dsl.design.COPPER_COUNTS`; the two live in different packages and no module imports both. Removing the unused mapping is c0085's to decide, not this change's.
   - No row of the Altium rule table is touched: this change adds no rule kind and no selector.
   - Rejected: keeping a refusal of 6 and 8, as this proposal first said. It contradicts c0085's "Layer stacks of any even count", and the code that gave it is gone.
   - Rejected: one more scenario inside c0085's "Complete board in an Altium build" instead of a requirement here. That requirement is c0085's delta, archived with release 0.3.0; a MODIFIED copy of it would carry its whole text for one scenario about the script's count.

9. **Code that reads the board's own copper list is not changed.** The copper check, the board frame and its padstack rows, fill, export, the DSN writer, the via span check of script copper and the views read `Board.layers`; measurement 4 runs them on 4, 6 and 8 layers. A script layer outside the table keeps its `kicad.copper.bad-layer` error.
   - Rejected: a count check in each consumer. The count is fixed once, where the table is created, and a board read from a file may hold any count.

10. **The oracle.**
    - *Tables* (`H-K-PCB-LAYERS`): the created test board with the table of n = 2, 4, 6 and 8 on both majors; a table of 3, written by the test's own row rule, as the negative control. Re-save on 10.0.6 only, because 9.0.9 has no `pcb upgrade`. A unit test asserts that `created_layers(n)` equals the test's row rule, so the probes judge the written table.
    - *Builds* (`H-K-BUILD-LAYERS`): the variant of measurement 4 for n = 4, 6 and 8 and both targets on 10.0.6. The four-layer row closes the half of the review's finding that no test builds four layers through fill, DRC and export.
    - *The 9.0.9 half* runs DRC and Gerbers on two committed fixtures, the six- and eight-layer target-9 boards filled by the 10.0.6 half, as `tests/data/kicad/fill/triad_t9_filled.kicad_pcb` does for c0015. 9.0.9 cannot fill (measurement 2), and unfilled inner zones leave GND and VIN unconnected. A hermetic test asserts that each fixture equals the target-9 build of its count except for fills, so a change of the build cannot leave a stale fixture.
    - Rejected: committing built projects. The build oracle forbids it, and the fixtures need only the board.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/kicad/layers.py` | `CREATED_COPPER_COUNTS = (2, 4, 6, 8)`; `inner_rows(copper) -> tuple[tuple[int, str, str, str | None], ...]`; `created_layers(copper: int) -> tuple[Layer, ...]`, `ValueError` naming the counts for any other value; `created_count(names: Sequence[str]) -> int | None`, the count whose created table has exactly these copper names; `INNER_ROWS` removed |
| `src/fenolite/dsl/design.py` | `COPPER_COUNTS = (2, 4, 6, 8)`; `inner_layers(copper) -> tuple[str, ...]`; `Design.copper_layers` (property); `board()`, `_planes`, `_zone_layers` on them; `INNER_LAYERS` removed |
| `src/fenolite/lens/build.py` | `build_design(…, copper: int, …)`; the hint of `plane_issues` |
| `src/fenolite/lens/preserve.py` | the message and hint of `layout.copper-mismatch` |
| `src/fenolite/cli/cmd_build.py` | the two `# type: ignore[arg-type]` of the `copper=` arguments removed |
| `src/fenolite/lens/altium_copper.py` | the text of `STACK_HINT` |
| `src/fenolite/cli/data/explain.toml` | the `fix` texts of `layout.copper-mismatch` and `build.plane-not-lowered` (no new code, so no new entry) |
| `tests/_boards.py`, `tests/_placed.py`, `tests/_coppercheck.py` | `copper: int` |
| `tests/unit/backends/kicad/test_layers_created.py` (new), `test_pcb_write.py` | the tables, the refusals (3 and 10 instead of 6), `created_count` |
| `tests/unit/dsl/test_board_layers.py` (new) | counts, inner layers, planes, zones, the two constants equal |
| `tests/unit/cli/test_build_command.py`, `test_build_preserve_command.py`, `test_build_altium.py`; `tests/unit/lens/test_altium_issues.py` | the build, rebuild and Altium scenarios |
| `tests/kicad/board/_layertables.py`, `test_layer_tables.py` (new); `tests/kicad/_probes.py` | the table probes |
| `tests/kicad/build/_layercases.py`, `test_layer_builds.py` (new) | the build probes |
| `tests/data/kicad/layers/l6_t9_filled.kicad_pcb`, `l8_t9_filled.kicad_pcb` (new, authored, rows in `tests/data/MANIFEST.toml`); `tests/unit/test_layer_fixtures.py` (new) | the 9.0.9 fixtures and their drift test |
| `docs/dsl.md`, `docs/lens.md`, `docs/altium.md`, `docs/formats/kicad/board.md` | counts, inner layers, plane hint, mismatch hint, six and eight layers in an Altium build, the table facts |

`Design.copper_layers` is the one new name a script sees. New names in all: `COPPER_COUNTS`, `inner_layers` and `Design.copper_layers` (DSL); `CREATED_COPPER_COUNTS`, `inner_rows` and `created_count` (KiCad backend). No model field, no issue code, no CLI flag, no result key and no source id is added.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PCB-LAYERS | A created layer table of 2, 4, 6 or 8 copper layers whose inner rows are `(2k + 2 "In<k>.Cu" signal)` after `F.Cu` loads on 9.0.9 (target-9 text) and 10.0.6 (both texts), gives one copper Gerber per copper layer, and keeps every copper row after `pcb upgrade --force` on 10.0.6; a table of 3 copper layers is refused by both majors (S-0020, S-0022, S-0029, S-0037, S-0058) | `tests/kicad/board/test_layer_tables.py` | probes `pcb-layers-<n>-t<M>` = `load` and `pcb-layers-gerbers-<n>-t<M>` = `equal` on each major that loads target M; `pcb-layers-resave-<n>-t<M>` = `equal` on 10.0.6; `pcb-layers-odd-t<M>` = `reject` |
| H-K-BUILD-LAYERS | A blink variant built with 4, 6 or 8 copper layers, a zone on every inner layer and script copper on the deepest one, for targets 9 and 10, fills on 10.0.6 with every zone filled, gives a DRC report with no violation and no unconnected item while the canary fires, exports one Gerber per copper layer whose X2 file function names its place in the stack, and rebuilds to the same bytes; on 9.0.9 the filled six- and eight-layer target-9 boards give the same report and Gerbers (S-0020, S-0029) | `tests/kicad/build/test_layer_builds.py` | probes `build-layers-<n>-t<M>` = `absent` and `build-layers-gerbers-<n>-t<M>` = `equal` on 10.0.6 for n = 4, 6, 8, and on 9.0.9 for the two fixtures |

Both start `INFERRED`, with the measurements of "Context" as their first record. Ids used without changing their level: `H-K-PCB-WRITE` (the four-layer table, `pcb-write-heads-*`), `H-K-FILL-SAVE`, `H-K-FILL-LOAD9`, `H-K-COPPER-VIAKINDS`, `H-A-PCB-CU-STACK`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| created tables of 6 and 8 layers | KICAD-VERIFIED (9.0.x, 10.0.x); re-save 10.0.x | `pcb-layers-*` |
| odd counts refused by KiCad | KICAD-VERIFIED (9.0.x, 10.0.x) | `pcb-layers-odd-*` |
| builds of 4, 6 and 8 layers: fill, DRC, export | KICAD-VERIFIED (10.0.x); DRC and export of the fixtures (9.0.x) | `build-layers-*` |
| DSL counts, inner layers, planes, zones | mechanical | unit tests |
| rebuild and its hint; plane hint | mechanical | unit tests |
| six and eight layers in an Altium build | mechanical on this change's side (layer names, hint); the written stack keeps c0085's evidence, which this change does not raise | unit tests |

No module's evidence constant changes: created tables are written under `pcb.WRITE_EVIDENCE`, which stays `INFERRED` for arbitrary designs; the two new rows are cited by the oracle tests and by the fact rows of `docs/formats/kicad/board.md`.

## Risks / Trade-offs

- [A board of 10 or more layers made in KiCad cannot be rebuilt from a script] → `check`, `fill`, `export` and the views read it; the `DslError` names the counts; the bound is an open question with its measured headroom.
- [A later 9.0.x or 10.0.x changes the numbering] → the table probes are pinned per version and fail first.
- [9.0.9 cannot re-save] → its `kicad-cli` has no `pcb upgrade`; 10.0.6 re-saves the target-9 text unchanged, and both majors share the numbering since 9.0.
- [A script imported `INNER_LAYERS`] → it was never re-exported by `fenolite.dsl`; `CHANGELOG.md` names `Design.copper_layers` and `inner_layers`.
- [The fixtures drift from the build] → the hermetic test of Decision 10.
- [The job file states a stack-up nobody chose] → as today at 2 and 4; c0101 writes one.

## Migration Plan

- Additive for scripts: counts 2 and 4 write the same bytes (`created_layers(2)` and `(4)` are unchanged; the unit test pins them), for both targets.
- A script of 6 or 8 layers built with `--target altium`, which the DSL refused before, now plans a PCB document.
- `INNER_LAYERS` and `INNER_ROWS` are removed; `inner_layers(copper)` and `inner_rows(copper)` replace them.
- The hints of `layout.copper-mismatch` and `build.plane-not-lowered` change their text; codes and severities do not.
- Rollback: restore the four guards; boards built with 6 or 8 layers stay valid KiCad boards that `check`, `fill` and `export` still read.

## Budget (3.5 days)

| part | days |
|---|---|
| entry check, registers, probe ids | 0.25 |
| layer table, its unit tests, `board.md` facts | 0.5 |
| DSL: counts, inner layers, planes, zones, unit tests, `dsl.md` | 0.5 |
| build and CLI types, plane hint, fixtures' types | 0.25 |
| rebuild message and hint, lens scenarios, `lens.md` | 0.25 |
| Altium scenarios, `STACK_HINT`, `altium.md` | 0.25 |
| table probes on both majors | 0.5 |
| builds of 4, 6 and 8 layers on 10.0.6, the two fixtures, the 9.0.9 half | 0.75 |
| closing | 0.25 |

Cut order: (1) the rebuild hint, keeping the error as it is; (2) the four-layer row of the build oracle; (3) the eight-layer rows of the build oracle, keeping the eight-layer table probes. Never cut: the counts in the DSL and the table, the table probes on both majors, and the six-layer build through fill, DRC and export on both majors.

## Open Questions

- **Should the bound go above 8?** Default: no, until a board needs it. Both majors load tables of up to 34 copper layers, so a raise is the two constants and probe rows, about 0.5 day per count with the build oracle.
- **Should a plane be written to KiCad, as a zone over the outline or as the row type `power`?** Default: no in this change; c0107 decides whether routing needs the marker.
- **Should a count mismatch rebuild on the script's count when the board holds Fenolite's table of another count?** Default: no; the error stays and its hint names both ways. c0102 owns count changes that keep the layout.
- **Are committed filled fixtures acceptable for the 9.0.9 half?** Default: yes, as c0015's `triad_t9_filled.kicad_pcb`, guarded by the drift test.
