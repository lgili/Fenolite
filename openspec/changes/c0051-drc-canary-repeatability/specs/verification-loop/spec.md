## MODIFIED Requirements

### Requirement: Check output is deterministic
Two `fenolite check --json` runs on the same project with the same `kicad-cli` SHALL give byte-identical stdout apart from `elapsed_ms` whenever the tool repeats its own reports, and Fenolite SHALL add no difference of its own.
- The output MUST NOT hold the DRC report's `date`, a temporary path, the home directory or an absolute path. Paths MUST be relative to the project root.
- Stages MUST follow `STAGE_ORDER`. Issues within a stage MUST be sorted by code, then `where`, then message.
- `project.files`, `project.skipped`, `tool_writes` and the keys of `by_type` and `by_severity` MUST be sorted.
- **What the tool does not repeat.** `kicad-cli` 10.0.6 writes its DRC report in another order from run to run, which the sorting above removes, and on boards with hundreds of violations it does not repeat the entries of the types `clearance`, `hole_clearance` and `unconnected_items` (`H-K-DRC-REPEAT`, `H-K-RT2-STABLE-2`). On such a board two runs MAY differ in the `drc.kicad` issues `kicad.drc.clearance`, `kicad.drc.hole-clearance` and `kicad.drc.unconnected-items`, in the `drc.kicad` summary values counted from them (`violations`, `unconnected`, `by_type`, `by_severity`, `types`), in the status of `drc.kicad` and in the exit code when those issues decide them. On a board with 499 or more `clearance` violations the canary state MAY also differ, between `fired` and `inconclusive` with reason `clearance-limit` (`H-K-DRC-LIMIT`; `kicad-oracle`, "Check canary injection"), and with it the issue `kicad.drc.rules-unchecked` and the evidence of `drc.kicad`. Nothing else MAY differ: the other stages, `tool_writes` and every issue of another code MUST be equal, and so MUST the canary state on a board below that count.
- `docs/cli-contract.md` MUST state under `check` which part of the output repeats and MUST name the three codes.

#### Scenario: Two runs on both majors
- **GIVEN** the authored built project
- **WHEN** `uv run pytest tests/kicad/check/test_check_oracle.py -k deterministic` runs `fenolite check --json` twice on 9.0.9 and on 10.0.6
- **THEN** the two stdouts are equal apart from `elapsed_ms`, and hold no `<tmp>`, home or absolute path

#### Scenario: Hermetic stages
- **WHEN** `fenolite check tests/data/kicad/board/two_layer.kicad_pcb --stages model.validate,erc.lite,roundtrip --json` runs twice
- **THEN** the two stdouts are equal apart from `elapsed_ms`

#### Scenario: A board whose DRC report the tool does not repeat
- **GIVEN** `kicad-demo-10-0-6-pcb-07` with a `{}` project and a `(version 1)` rules file, on 10.0.6
- **WHEN** `uv run pytest "tests/kicad/check/test_canary.py::test_two_run_demo_boards[kicad-demo-10-0-6-pcb-07]"` runs the oracle of `drc.kicad` twice
- **THEN** the two outcomes agree in the canary state (the board holds fewer than 499 `clearance` violations), the return code, `tool_writes` and every entry of a type other than `clearance`, `hole_clearance` and `unconnected_items`

#### Scenario: The contract names what does not repeat
- **WHEN** `uv run pytest tests/unit/test_drc_repeat.py -k contract` reads `docs/cli-contract.md`
- **THEN** its `check` section names `kicad.drc.clearance`, `kicad.drc.hole-clearance` and `kicad.drc.unconnected-items` as the issues that can differ between two runs, and the reason `clearance-limit`
