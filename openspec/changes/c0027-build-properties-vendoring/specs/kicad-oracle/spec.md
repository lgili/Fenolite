## ADDED Requirements

### Requirement: Vendored projects and user properties pass the oracle
`tests/kicad/build/` (marker `needs_kicad`, major-aware) SHALL prove on the running `kicad-cli` that a built project whose footprints come from global or template rows is self-contained once they are vendored, and that user properties written by the build load and survive. Every case MUST build a blink variant into a temporary folder, run `kicad-cli` through c0009's `KicadCli.run` on a copy, and judge DRC only from the JSON report read with c0017's `read_drc_report`, never from the exit code (c0017, "DRC verdicts come from the JSON report").
- **Bench.** `tests/kicad/build/_vendorcases.py` makes, in a temporary folder:
  - a fake global library: a copy of the CC0 `tests/data/libs/Mini_v9.pretty` and `Mini_v9.kicad_sym`, named by the rows `Mini` of the global tables `<D>/<M>.0/fp-lib-table` and `sym-lib-table` of a configuration folder `D`, for both majors;
  - `D_alt`, the same with a copy whose `Mini_R_0603` pad `1` is moved 0.05 mm along X;
  - the blink built from a folder without project tables, with `config_home=D`: not vendored (c0011's rule, later `vendor="project"`), and vendored, with its placed footprints copied into `lib/Mini.pretty/` and one project row (by file copies of the bench while the probes run before this change's build code, later by `vendor="all"`);
  - the property board, whose user properties are appended through `embed.with_property` before `embed.place_footprint` (through the model API while the probes run first, later by the build).
- **Configuration.** A configuration folder MUST reach `kicad-cli` only as the explicit `env` entry `KICAD_CONFIG_HOME` of `KicadCli.run`; every other run uses the runner's empty configuration folder.
- **Probes first.** The cases MUST be probes of c0017's `tests/kicad/_probes.py`. Each probe maps its result to one outcome of c0017's closed set, and the `-t9` probes run on majors 9 and 10, the `-t10` probes on major 10:
  - `vendor-global-t<M>`: `equal` when the vendored build gives no `lib_footprint_issues` and no `lib_footprint_mismatch` while the build that is not vendored gives one `lib_footprint_issues` for each footprint; `absent` when `lib_footprint_issues` remain with vendoring; `different` when a `lib_footprint_mismatch` appears; `inconclusive` when the build that is not vendored gives no `lib_footprint_issues`; `reject` when no report is written.
  - `vendor-shadow-t<M>` (with `D_alt`): `present` when the build that is not vendored gives exactly one `lib_footprint_mismatch` (the control: the global table was read) and the vendored build gives none; `absent` when the vendored build gives it too; `inconclusive` when the control gives none.
  - `vendor-hide-t<M>` (with `D`): the vendored build with `Mini_LED_THT_3mm.kicad_mod` removed from `lib/Mini.pretty/`. `present` when it gives exactly one `lib_footprint_issues`, for `D1`, while the build that is not vendored gives no library violation with `D` (the control); `absent` when it gives none; `inconclusive` when the control gives a library violation.
  - `vendor-props-t<M>`: the vendored property board, with user properties on `R1` (two, one value holding `"`, `\` and `µ`) and on `D1` (bottom side). `equal` when its report holds no `lib_footprint_issues` and no `lib_footprint_mismatch`, as the plain vendored build's; `different` otherwise; `reject` when no report is written.
  - `vendor-resave-t<M>` (major 10): after `pcb upgrade --force` of that board, `present` when `read_board` gives every user property with its value and every user property node keeps `(hide yes)`; `absent` otherwise; `reject` when the upgrade fails.
  - `vendor-dupname-t10` (major 10): the vendored board with, inserted by text after `R1`'s last property, a second `Datasheet` property and the properties `datasheet` and `reference`. After `pcb upgrade --force`, `present` when one `Datasheet` node remains, holding the inserted value, and `datasheet` and `reference` are kept; `absent` when two `Datasheet` nodes remain; `different` otherwise.
- **Stop rules,** applied before any build code of this change is written: a `vendor-global` outcome other than `equal`, on either major, stops the vendoring half until the table form is corrected; a `vendor-props` outcome other than `equal` stops the property half until the property form is corrected. The `vendor-shadow`, `vendor-hide`, `vendor-resave` and `vendor-dupname` outcomes change no behaviour: they are recorded and written into `docs/dsl.md` and the format pages, and the reserved names stay whatever `vendor-dupname` gives.
- **Acceptance.** `tests/kicad/build/test_vendor_oracle.py` asserts the expected outcomes: `test_global_vendored` (`equal`), `test_shadow` (`present`), `test_hidden_items` (`present`), `test_user_properties` (`equal`, and `present` for the re-save on 10.0.6) and `test_duplicate_field_name` (`present`, 10.0.6). Target 9 runs on 9.0.9 and 10.0.6, target 10 on 10.0.6.
- **Official libraries.** Where they are installed (marker `needs_libs`), `tests/libs/test_build_official.py` MUST build `examples/blink_official/design.py` into `tmp_path` with the default vendoring and, with `needs_kicad` too, `kicad-cli pcb drc` on that folder with an empty configuration MUST give no `lib_footprint_issues` and no `lib_footprint_mismatch`. Only counts are recorded, and nothing built from it is committed (`ip-hygiene`).
- The outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, which hold only the version, the probe ids and their outcomes (c0017). The facts go to `docs/formats/kicad/libraries.md` and `board.md` as rows with `H-K-VENDOR-*`. Built files and library copies MUST NOT be committed.

#### Scenario: Vendored global footprints pass the library check
- **GIVEN** the blink built from the fake global library for target 10
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_global_vendored` runs on 10.0.6
- **THEN** the vendored build's report holds no `lib_footprint_issues` and no `lib_footprint_mismatch`, and the build that is not vendored gives three `lib_footprint_issues`

#### Scenario: The project row wins over the global row
- **GIVEN** the vendored blink and the configuration folder `D_alt`
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_shadow` runs on 10.0.6 and on 9.0.9
- **THEN** the build that is not vendored gives exactly one `lib_footprint_mismatch` for `R1`, and the vendored build gives none

#### Scenario: Items missing from the vendored library are not taken from the global one
- **GIVEN** the vendored blink without `lib/Mini.pretty/Mini_LED_THT_3mm.kicad_mod`, and the configuration folder `D`
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_hidden_items` runs
- **THEN** the report holds exactly one `lib_footprint_issues`, for `D1`

#### Scenario: User properties survive a re-save
- **GIVEN** the vendored blink with user properties built for target 9
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_user_properties` runs on 10.0.6
- **THEN** its report holds no library violation, and after `pcb upgrade --force` `read_board` gives `R1` the value with `"`, `\` and `µ` unchanged, and every user property node holds `(hide yes)`

#### Scenario: A duplicate field name is merged
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py::test_duplicate_field_name` runs on 10.0.6
- **THEN** after the re-save `R1` holds one `Datasheet` node with the inserted value, and the `datasheet` and `reference` properties are unchanged

#### Scenario: 9.0 job
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** `uv run pytest tests/kicad/build/test_vendor_oracle.py -rA` runs in the `kicad-9` job
- **THEN** every target-9 case without a re-save runs and passes, and the re-save, duplicate-name and target-10 cases are skipped by `kicad_min_major(10)`

#### Scenario: Probe outcomes pinned
- **GIVEN** `docs/evidence/kicad/probes/10.0.6.json` regenerated with `FENOLITE_PROBES_WRITE=1` after `uv run pytest tests/kicad/build/test_vendor_probes.py -rA`
- **WHEN** `uv run pytest tests/kicad/test_probe_results.py` runs on the local KiCad 10.0.6
- **THEN** it passes, and the file holds an outcome for every `vendor-*` probe of majors 9 and 10

#### Scenario: Official libraries where they are installed
- **GIVEN** the official libraries found by the `needs_libs` census and a local `kicad-cli` 10.0.6
- **WHEN** `uv run pytest -m "needs_libs and needs_kicad" tests/libs/test_build_official.py -rA` runs
- **THEN** the official blink built into `tmp_path` holds its three footprints under `lib/`, its report holds no `lib_footprint_issues` and no `lib_footprint_mismatch`, and `uv run pytest tests/residue/test_official_libs.py` passes
