## ADDED Requirements

### Requirement: Written boards load and count on both majors
`tests/kicad/board/test_triad.py` (markers `needs_kicad`, major-aware) SHALL write the triad of `tests/kicad/board/_triad.py` with `write_board` and check it with the running `kicad-cli`. Every run MUST go through c0009's package runner on a copy in `tmp_path`, with a `{}` project file next to the board, passed through the `files` argument that this change adds to every `KicadCli` helper, and an empty `KICAD_CONFIG_HOME`.
- **Emit check.** Before any `kicad-cli` run, `check_emittable` on the parsed target-9 and target-10 texts, each with its own target, MUST return no issue.
- **Load.** On 9.0.9 the target-9 text, and on 10.0.6 the target-10 text, MUST load with `KicadCli.load_board_svg`.
- **Report.** `read_drc_report` MUST parse the DRC report of each loaded triad.
- **Placements.** `pcb export pos --format csv --side both` MUST list 3 footprints whose references, positions, rotations and sides equal the model, compared through c0009's pos comparison.
- **Counts.** On 10.0.6, the footprint and pad counts of `pcb export stats --format json` MUST equal the model's.
- **Negative control.** On 9.0.9, loading the target-10 text MUST exit 3.
- **Created heads.** The created test board `tests/_boards.py::created_board(4)`, which holds one created entity of every `CANONICAL_ORDER` head, every name of `pcb.FLOOR_HEADS` and the 4-copper layer table, MUST pass the emit check and load: the target-9 text on 9.0.9 and the target-10 text on 10.0.6 (probe ids `pcb-write-heads-9` and `pcb-write-heads-10`).

`tests/kicad/board/test_net_forms.py` SHALL write the triad and `tests/data/kicad/board/two_layer.kicad_pcb` for each target the running major loads. Each text MUST load, and the net partition of `pcb export ipcd356` MUST equal the model's nets (`H-K-TOK-NETNAME`, `H-K-TOK-OBSOLETE`).

`tests/kicad/board/test_genver.py::test_generator_version_variants` SHALL load the triad texts with `generator_version` absent, `"9.0"`, `"10.0"` and `"fenolite-x"`: the target-9 text on both majors and the target-10 text on 10.0.6. Each outcome MUST be recorded under a `pcb-genver-*` probe id (`H-K-GENVER`). The emitted value `"<target>.0"` MUST load.

#### Scenario: Triad on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_triad.py` runs
- **THEN** the target-10 triad and the target-10 created test board load, pos lists `R1` top at 0°, `D1` bottom at 90° and `U1` top at 30° at the model's positions, and `pcb export stats` counts 3 footprints and the model's number of pads

#### Scenario: Triad on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the `kicad-9` job
- **WHEN** `uv run pytest tests/kicad/board/test_triad.py` runs
- **THEN** the target-9 triad and the target-9 created test board load, the triad's pos rows equal the model, and loading the target-10 triad text exits 3

#### Scenario: Authored board in both net forms
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_net_forms.py` runs
- **THEN** `two_layer.kicad_pcb` written for target 9 and for target 10 loads, and each IPC-D-356 export puts `R1` pin 2 and `D1` pin 2 on one net, which the model calls `LED_A`

#### Scenario: Generator version variants recorded
- **GIVEN** `kicad-cli` 9.0.9
- **WHEN** `uv run pytest tests/kicad/board/test_genver.py` runs
- **THEN** the four variants of the target-9 text each record `load` or `reject` under their probe id, and the `"9.0"` variant records `load`

### Requirement: Placed footprints match their library definitions
`tests/kicad/board/test_flip_oracle.py` (markers `needs_kicad`, major-aware) SHALL check `place_footprint` against three independent `kicad-cli` outputs:
- **Bench.** `Mini_R_0603`, `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm` placed at 0°, 30°, 90° and 180° on the top and on the bottom: 24 placements on one board written for the running major in `tmp_path`. The folder holds a `{}` project file, a copy of `tests/data/libs/Mini.pretty` (10.0.6) or `tests/data/libs/Mini_v9.pretty` (9.0.9), and a project `fp-lib-table` whose row `Mini` points at `${KIPRJMOD}/<that folder>`. Every definition MUST be read with `read_footprint(path, library="Mini")` on both majors, so every placement is named `Mini:<name>`. `KICAD_CONFIG_HOME` MUST be empty.
- **Placements.** On both majors, the side and rotation that `pcb export pos --format csv --side both` gives for all 24 placements MUST equal the model (`test_flip_angle`).
- **Pads.** On both majors, every pad record of `pcb export ipcd356`, taken relative to the file's first record, MUST equal `at + R(θ)·stored` relative to that record's model pad within ±2 export units (±5 080 nm) per axis, through c0009's comparison in `tests/kicad/board/_frame.py` (`test_bottom_store`). No absolute bound is asserted, because the export origin is unknown. `R` fields are recorded and not asserted (`test_pad_angles`).
- **Library parity.** On 10.0.6, `pcb drc` MUST report no `lib_footprint_mismatch` for the 24 placements.
- **Negative controls.** Three boards, each with one bottom QFP at 30°: unmirrored bottom children; relative pad angles (θ not added); the footprint written at −θ with every child unchanged. On 10.0.6, each MUST give exactly one `lib_footprint_mismatch`.
- **Missing-table control.** On 10.0.6, an exact placement on a board without `fp-lib-table` MUST give `lib_footprint_issues` (`test_lib_drc`). When it does not, the run MUST be recorded `inconclusive` and the library-parity assertions MUST fail, never pass.
- **KiCad 9.0.** On 9.0.9, the DRC outcomes of the bench, the three controls and the missing-table control MUST be recorded under `pcb-libdrc-*` probe ids, `pcb-libdrc-missing-table` included, and MUST NOT fail the test (`H-K-LIB-DRC`).

Before any oracle uses them, the authored files `tests/data/libs/Mini_v9.pretty/Mini_LED_THT_3mm.kicad_mod` and `Mini_QFP-32_7x7mm_P0.8mm.kicad_mod` MUST pass c0008's `tests/kicad/libs/test_mini_oracle.py` on 9.0.9: they load, and they re-read equal after `fp upgrade --force`.

#### Scenario: Exact placements on KiCad 10
- **GIVEN** `kicad-cli` 10.0.6 and the 24-placement bench
- **WHEN** `uv run pytest tests/kicad/board/test_flip_oracle.py` runs
- **THEN** the report holds no `lib_footprint_mismatch`, every pos row and IPC-D-356 pad matches the model, and each negative control gives exactly one `lib_footprint_mismatch`

#### Scenario: Unmirrored control detected
- **GIVEN** the bottom QFP at 30° written with its children not mirrored about local X
- **WHEN** DRC runs on 10.0.6
- **THEN** the report holds exactly one `lib_footprint_mismatch`, whose item uuid is that footprint's uuid

#### Scenario: Silent library table
- **GIVEN** `kicad-cli` 10.0.6 whose missing-table control reports no `lib_footprint_issues`
- **WHEN** the flip oracle runs
- **THEN** the outcome `inconclusive` is recorded for `pcb-libdrc-missing-table` and `test_lib_drc` fails with a message naming `H-K-LIB-DRC`

#### Scenario: Silent library table on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 whose missing-table control reports no `lib_footprint_issues`
- **WHEN** the flip oracle runs
- **THEN** the outcome is recorded under `pcb-libdrc-missing-table` and `test_lib_drc` does not fail

#### Scenario: Bottom pads on KiCad 9
- **GIVEN** `kicad-cli` 9.0.9 in the `kicad-9` job
- **WHEN** `uv run pytest tests/kicad/board/test_flip_oracle.py` runs
- **THEN** every IPC-D-356 pad of the 12 bottom placements, relative to the first record, lies within ±2 export units per axis of the model, and the DRC outcomes are recorded without failing the test

#### Scenario: Nine-format mini footprints
- **GIVEN** `kicad-cli` 9.0.9
- **WHEN** `uv run pytest tests/kicad/libs/test_mini_oracle.py` runs
- **THEN** `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm` of `Mini_v9.pretty` load and re-read equal after `fp upgrade --force`

### Requirement: DRC verdicts come from the JSON report
Every oracle test and every command that judges a DRC outcome SHALL read it from the JSON report, through `KicadCli.drc` and `read_drc_report`.
- `KicadCli.drc(board, *, files=None)` MUST run `pcb drc --format json --severity-all -o <out> <board>` through c0009's runner on a copy, and MUST NOT pass `--exit-code-violations`. `DrcRun.report` MUST be `None` when no report was written.
- The exit code of `pcb drc` MUST be used only as a load signal.
- A report without violations MUST NOT count as evidence that a library table, a project file or a custom rules file was loaded. Every such proof MUST carry a control that fires only when the file was loaded: the missing-table control here, the canary in the rules proofs.
- `tests/kicad/board/test_drc_report.py::test_drc_json_strict` MUST settle `H-K-DRC-JSON` on both majors: the report parses with `NaN` and `Infinity` rejected, holds the 7 required top-level keys, and `read_drc_report` accepts it. Whether `ignored_checks` is present MUST be recorded per major under the probe id `pcb-drc-ignored-checks`.

#### Scenario: Strict report on both majors
- **GIVEN** the triad written for the running major
- **WHEN** `uv run pytest tests/kicad/board/test_drc_report.py` runs on 9.0.9 and on 10.0.6
- **THEN** each report parses as strict JSON with `source`, `date`, `kicad_version`, `violations`, `unconnected_items`, `schematic_parity` and `coordinate_units`, and `read_drc_report` returns a `DrcReport`

#### Scenario: Exit code is not a verdict
- **GIVEN** a fake `kicad-cli` that exits 0 and writes a report holding one `clearance` violation
- **WHEN** `KicadCli.drc` runs
- **THEN** the arguments hold no `--exit-code-violations`, and `run.report.of_type("clearance")` returns one violation

#### Scenario: No report written
- **GIVEN** a fake `kicad-cli` that exits 3 and writes no report
- **WHEN** `KicadCli.drc` runs
- **THEN** `run.report is None` and `run.run.returncode == 3`

#### Scenario: Extra files next to the board
- **GIVEN** a fake `kicad-cli` that lists its working directory
- **WHEN** `load_board_svg(board, files={"board.kicad_pro": pro, "fp-lib-table": table})` runs
- **THEN** the listing holds the board copy, `board.kicad_pro` and `fp-lib-table`, and the caller's files are unchanged

### Requirement: Written boards keep read content
`tests/kicad/board/` SHALL prove on the running `kicad-cli` that writing a read board keeps its content:
- **9 → 10** (`test_cross_version.py`, `needs_corpus`, `kicad_min_major(10)`). Every non-heavy demo board whose header maps to major 9 is read and written for target 10. The text MUST load on 10.0.6. The comparison first removes from the source design's `kicad` bags every `Opaque` slot whose fragment is a whole node that a target-10 write removes: the root `(net 0 "")`, `(net 0)` references, and zone `net_name` and `filled_areas_thickness`. The `opaque_count` of the re-read MUST equal the source's count minus the number of slots removed. Its canonical JSON MUST equal the source's after that removal, apart from the board's header bag, net numbers and the fragments of `Opaque` slots, which net-form rewriting and obsolete rows may change inside. Every source fragment that holds no `net` node and no node of an `until_major = 9` row MUST have its digest among the re-read's `opaque_digests`. Same-target writes keep exact equality of `opaque_count`.
- **Refusals** (`test_cross_version.py`). The triad written for 10, read back and written for 9, MUST raise `DowngradeRefusedError`. `tests/data/kicad/tokens/old/old.kicad_pcb` MUST raise `LegacyEditRefusedError`.
- **Lossy embedding** (`test_cross_version.py`). `Mini_R_0603` read from `Mini.pretty` and placed for target 9 MUST raise `LossyWriteError`. With `allow_lossy=True` the write MUST succeed with one `kicad.board.dropped-too-new` warning, and the text MUST load on 9.0.9.
- **uuids** (`test_uuid_keep_written.py::test_uuid_keep_written`, `kicad_min_major(10)`). On 10.0.6, the written triad and its `pcb upgrade --force` copy MUST have equal unmasked `uuid` multisets (`H-K-UUID-KEEP`, Fenolite-written half).
- **Unknown child** (`test_unknown_child.py`). `tests/data/kicad/board/dimension.kicad_pcb` is read, one segment is moved in the model, and the board is written for 9 and for 10. The `dimension` node MUST reappear tree-equal to the source node, at its source index for target 9 and between the same neighbouring items for target 10, whose root has no net table. `opaque_count` MUST be equal for target 9, and equal to the source's count minus the slots removed as for the demos for target 10. Each text MUST load on its major.

#### Scenario: Demo boards converted to 10
- **GIVEN** `kicad-cli` 10.0.6 and the fetched corpus
- **WHEN** `uv run pytest tests/kicad/board/test_cross_version.py -k demos` runs
- **THEN** every major-9 demo written for target 10 loads and re-reads equal apart from header, net numbers and the removed slots, with `opaque_count` lowered by exactly the number of removed slots, or the test fails naming the board

#### Scenario: Written uuids survive a KiCad re-save
- **GIVEN** `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/kicad/board/test_uuid_keep_written.py` runs
- **THEN** the unmasked `uuid` multiset of the written triad equals that of its upgraded copy

#### Scenario: Unknown child survives a write
- **GIVEN** `dimension.kicad_pcb` read, with one segment moved
- **WHEN** it is written for target 9 and loaded on 9.0.9
- **THEN** the text loads, the `dimension` node is at its source index and tree-equal to the source node, and `opaque_count` equals the source's

### Requirement: Probe results per kicad-cli version
`tests/kicad/_probes.py` SHALL define the closed mapping `PROBES` (probe id → probe function and the majors it runs on) and `run(probe_id) -> str`, memoised per test session. An outcome MUST be one of `load`, `reject`, `present`, `absent`, `equal`, `different`, `inconclusive` and `timeout`.
- Oracle tests MUST assert on `run(…)` rather than run a probe themselves.
- `tests/kicad/test_probe_results.py` MUST run every probe of the running major and compare the outcomes with `docs/evidence/kicad/probes/<version>.json`. `<version>` is the first line of `kicad-cli version` restricted to `[0-9A-Za-z.+-]`.
- With `FENOLITE_PROBES_WRITE=1`, the test MUST write that file instead of comparing.
- A missing file for the running version MUST fail the test with a message naming `FENOLITE_PROBES_WRITE`.
- The file MUST hold only the version, the probe ids and their outcomes, and MUST pass the residue scan.
- The `kicad-9` and `kicad-10` jobs MUST run the comparison in required mode.

#### Scenario: Drift detected
- **GIVEN** a committed `docs/evidence/kicad/probes/10.0.6.json` that records `absent` for `pcb-libdrc-missing-table`
- **WHEN** a run on 10.0.6 yields `present` for that probe
- **THEN** `uv run pytest tests/kicad/test_probe_results.py` fails naming the probe id and both outcomes

#### Scenario: Missing results file
- **GIVEN** a `kicad-cli` whose version has no file under `docs/evidence/kicad/probes/`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs without `FENOLITE_PROBES_WRITE`
- **THEN** it fails with a message naming `FENOLITE_PROBES_WRITE`

#### Scenario: Results regenerated
- **WHEN** `FENOLITE_PROBES_WRITE=1 uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** `docs/evidence/kicad/probes/10.0.6.json` holds one outcome per probe of major 10, and `uv run python tools/residue/scan.py` exits 0
