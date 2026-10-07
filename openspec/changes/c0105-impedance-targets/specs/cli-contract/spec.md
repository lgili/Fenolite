## ADDED Requirements

### Requirement: Impedance command
`fenolite impedance PATH [--estimate] [--out FILE]` SHALL be registered by `src/fenolite/cli/cmd_impedance.py` with `mutates=True`, and SHALL give the impedance table of a project ("Impedance table for the fabricator"), written as a CSV file only with `--out`.
- **Project.** `PATH` MUST resolve as for `bom` (a `.kicad_pcb`, a `.kicad_pro` or a project folder), with its usage and input errors. An Altium document or project MUST get the error that `bom` gives for it: no Altium record is read into a target. On built input the design MUST be the `.fenolite/` model; on native input, the board read with its project applied ("Tuning profiles are read into impedance targets"). `result.source` MUST be `model` or `project`.
- **Result.** `result` MUST hold `source`, `columns` (`COLUMNS`), `rows` (one object per row, lengths in nanometres) and `counts` (`targets`, `rows`, `estimated`, `left_out`). A design without targets MUST give one `impedance.none` info and exit 0.
- **`--estimate`.** Each row MUST gain `estimate`: `{"mohm", "suggested_width", "in_range", "form", "reason"}` from `analysis.impedance.estimate` and `solve_width` for the target's `ohms`; `mohm` and `suggested_width` MUST be `null` when no form applies, `reason` naming why, and `suggested_width` MUST be `null` when `ohms` is empty. The issues MUST follow the table of `exports.impedance.ISSUE_CODES`, and a row left out for a missing stack-up or permittivity MUST count in `left_out`. The envelope evidence MUST combine the source's level with `analysis.impedance.EVIDENCE`, and MUST be `UNVERIFIED` when a row was left out.
- **Writes.** With `--out FILE`, the command MUST return one `PlannedWrite` of kind `impedance` whose bytes are `exports.impedance.render_csv` of the rows (with the estimates under `--estimate`); without it, none. The mutation protocol applies, and the project folder MUST NOT change otherwise. The command takes no `--manifest`, and the written table is no manifest entry (`manufacturing-exports`, "Artefact states", is unchanged).
- **Registered everywhere.** The command MUST be covered by "Consistency test covers every command" and named by "Contract page names every command" and by `fenolite capabilities`; every issue code it can give MUST have a table in `src/fenolite/cli/data/explain.toml`.
- **Determinism.** Two runs on an unchanged project MUST give the same stdout apart from `elapsed_ms`, and the same file bytes.
- `example_args` MUST be `(EXAMPLE_BOARD,)` and `mutation_example_args` `(EXAMPLE_BOARD, "--out", "impedance.csv")`; neither runs a subprocess.

#### Scenario: Built project
- **GIVEN** the design of "Two targets synthesised for target 10" built into `tmp_path`
- **WHEN** `fenolite impedance <dir> --json` runs
- **THEN** the exit code is 0, `result.source` is `model`, `result.rows` holds three rows, `result.counts.targets` is 2, and no file is written

#### Scenario: Estimates
- **WHEN** `fenolite impedance <dir> --estimate --json` runs on the same project
- **THEN** the `SE50` row on `F.Cu` has `estimate.mohm` equal to `microstrip_mohm(350_000, 200_000, 35_000, "4.3")`, the `USB90` row has `estimate.mohm` `null` with `reason` `differential`, `issues` hold one `impedance.estimate-unsupported` info, and `evidence.level` is `INFERRED`

#### Scenario: Confirmation required
- **WHEN** `fenolite impedance <dir> --out impedance.csv` runs without `--confirm`
- **THEN** the exit code is 4, `result.plan` lists `impedance.csv`, and no file is written; with `--confirm`, `receipt.written` lists it with its SHA-256

#### Scenario: Project without targets
- **WHEN** `fenolite impedance tests/data/kicad/board/two_layer.kicad_pcb --json` runs
- **THEN** the exit code is 0, `result.rows` is empty and `issues` hold one `impedance.none` info
