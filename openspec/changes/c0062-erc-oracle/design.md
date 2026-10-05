## Context

- **Scope.** Plan D9, stage 2: "`erc.lite` — v0.1 only three rules, `INFERRED`, marked for removal in v0.2a, when `kicad-cli sch erc --format json` becomes the source (`KICAD-VERIFIED`)", and stage 3: "`--schematic-parity` from v0.2a". Plan v0.2a acceptance: "`sch erc` exit 0 on the examples", "`--schematic-parity` without findings on the examples", and "RT0 to RT2 (ERC)" on the demo schematics. The living `verification-loop` says of parity: "`schematic_parity` entries MUST be counted in `summary` and MUST NOT be mapped, because no parity check runs before v0.2a".
- **What exists.**
  - `KicadCli.run` and `KicadCli.drc` on copies with an empty configuration folder; `projectset.project_set`, which never copies `.kicad_sch` and `sym-lib-table`; `KicadOracle.drc` with the rules canary; `read_drc_report`, which already parses `schematic_parity`.
  - `checks.stages.STAGE_ORDER` with `erc.lite` second, and `checks.erc_lite` with `REMOVE_IN = (0, 2)`: the suite fails by design once the package version reaches 0.2.
  - c0060's `sch.sheet_files`; c0061's built schematic, symbol libraries and `sym-lib-table`.
  - c0044 (proposed, v0.3) runs the three rules on Altium documents through its own pipeline and asks that this change "keeps the three rules for document input and moves `REMOVE_IN` to the KiCad use only".
- **Observed at proposal time** (2026-10-04) on `kicad-cli` 9.0.9 (pinned image) and 10.0.6 (macOS), on a hand-made sheet for the built blink:
  - `sch erc` takes `--format json|report`, `--units`, `--severity-all`, `--severity-error`, `--severity-warning`, `--severity-exclusions`, `--exit-code-violations`, `-o` and `--define-var` on both majors.
  - The JSON report has `$schema`, `source`, `date`, `kicad_version`, `coordinate_units`, `included_severities` and `sheets`; each sheet has `path`, `uuid_path` and `violations`; each violation has `type`, `severity`, `description` and `items`; each item has `uuid`, `description` and `pos`. 10.0.6 adds `ignored_checks` (key and description per ignored check); 9.0.9 has no such key. The public schema says the same and makes `excluded` optional (S-0330, S-0331).
  - With `coordinate_units` `mm`, the item at sheet position (139.7, 59.69) mm is reported at `x` 1.397 and `y` 0.5969, on both majors: positions are divided by 100.
  - Types seen: `pin_not_connected`, `pin_not_driven`, `power_pin_not_driven` (errors); `lib_symbol_issues`, `multiple_net_names` (warnings); for a label on a single pin, `isolated_pin_label` on 10.0.6 and `global_label_dangling` on 9.0.9.
  - Exit codes: 0 with a report when `--exit-code-violations` is absent; 5 with it when violations exist; 3 and no report for a schematic that does not load (a broken file, a missing file, a version above the tool's; 10.0.6).
  - `sch erc` writes `<stem>.kicad_prl` beside its input.
  - `pcb drc --schematic-parity` exists on both majors and fills `schematic_parity` with entries of the DRC violation shape (`net_conflict`, `footprint_symbol_mismatch`, `missing_footprint`, `extra_footprint` seen, all warnings); without the flag the list is empty.
- **Constraints.** `checks` stays backend-free. `check` stays read-only: every tool runs on copies. Stdlib only.

## Goals / Non-Goals

**Goals:**
- KiCad's ERC verdict in `check`, with the same guarantees as its DRC verdict: on a copy, from the JSON report, located as `REF-PIN`, with its own evidence.
- Parity findings as issues.
- One ERC source for KiCad input: the three rules leave the KiCad pipeline.
- RT2 for schematics over the corpus.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A canary for ERC. ERC has no rules file that KiCad can silently drop; a project that ignores a check is visible in `ignored_checks` on 10.0 and in the project file on both.

## Decisions

1. **Probe first.** Task group 2 pins on both majors: the report keys, the position scale, exit codes with and without a loadable schematic, the types and severities of five controls and their change through the project's `erc.rule_severities`, repeatability of two runs, the copy set against a copy of the whole folder, and parity with and without the flag. The reader and the stage are written after the probes.

2. **Runner.** `KicadCli.erc(schematic, *, files=None, env=None) -> ErcRun` runs `sch erc --format json --severity-all -o <out> <schematic>` through `KicadCli.run` on a copy. `--exit-code-violations` is never passed: the exit code is a load signal, and every verdict comes from the report. `ErcRun(run, report)`; `report` is `None` when no report was written.

3. **Neutral report.** `backends.base` gains `ErcItem(uuid, description, position, where="")`, `ErcViolation(type, description, severity, items, excluded, sheet)` and `ErcReport(source, date, kicad_version, coordinate_units, violations, ignored_checks, included_severities)`, with `entries()` as `DrcReport` has: the sorted tuple of `(sheet, type, severity, excluded, items)` without uuids, for comparing two runs.
   - `sheet` is the human-readable path of the sheet (`/`, `/Child/`), and violations keep report order, sheets in report order.

4. **Reader.** `backends/kicad/erc.py::read_erc_report(text, *, file="", major=None, issues=None) -> ErcReport`, strict JSON with numbers kept as text, as `read_drc_report`.
   - Required keys: `source`, `date`, `kicad_version`, `sheets`; in a sheet `path`, `uuid_path`, `violations`; in a violation `type`, `description`, `severity`, `items`. A missing key raises `FormatError`. `excluded` defaults to false; `ignored_checks` and `included_severities` are kept when present; unknown keys are ignored.
   - **Positions.** A coordinate is converted to nm from `coordinate_units` and then multiplied by `erc.POSITION_SCALE[<major>]`, 100 on both majors if `H-K-ERC-POS` holds. A major whose probe gives another factor gets that factor, and a major without a proved factor leaves `position` as converted, with the info `kicad.erc.position-unscaled`.
   - The schema file is not vendored and not read at run time; `docs/formats/kicad/erc.md` describes the report in Fenolite's words with key names only.

5. **Copy set.** `projectset.project_set` also plans, when `<stem>.kicad_sch` exists beside the board: that file; every sheet file `sch.sheet_files` lists inside the root; `sym-lib-table` and each `${KIPRJMOD}` row inside the root (a `.kicad_sym` file or a folder of them); and the drawing sheet named at `/schematic/page_layout_descr_file` of the project. Skip reasons are the existing ones; a root schematic that cannot be read still joins the set alone, and KiCad decides what to do with it.
   - One copy set serves DRC and ERC: the parity test needs the schematic in the DRC run, and two sets would let the two runs see different projects.
   - `H-K-CHECK-COPYSET` is proved again with a schematic in the folder, and `H-K-ERC-COPYSET` states the same for ERC.
   - Global symbol libraries are not visible to the isolated tool, as global footprint libraries are not. A native project that relies on them gets `lib_symbol_issues` warnings; `docs/cli-contract.md` says why. Built projects carry their symbols (c0061).

6. **Oracle.** `backends.base.ErcOracle` (`@runtime_checkable`): `name`, `version()`, `erc(project) -> ErcOutcome(report, tool_version, tool_writes, outcome, returncode, message, evidence)`. `KicadOracle.erc` runs `KicadCli.erc` on the root schematic with the copy set, and fills each item's `where`:
   - `erc.item_locations(trees, project) -> Mapping[tuple[str, str], str]` walks the parsed trees of the copied sheet files and maps (sheet instance path, uuid) to `REF-PIN` for the uuid of a `pin` child of a symbol, to `REF` for a symbol's uuid, and to the label text for a label's uuid; the reference is the one the symbol's `instances` give for that sheet path, so a sheet used twice gives two references.
   - An item whose uuid is not in the map keeps `where == ""`, and the stage falls back to its position.
   - Rejected: locating items from their description text. The text is KiCad's prose and may change with a version or a language.

7. **Stage `erc.kicad`.** `checks/erc.py::erc_stage(oracle, project) -> StageResult`, second in `STAGE_ORDER`, in the place of `erc.lite`, a default stage and an oracle stage.
   - Runs on built and on native input alike. Skipped with reason `no-schematic` when the project set holds no `<stem>.kicad_sch`, and with `unsupported-oracle` when the oracle is not an `ErcOracle`. Neither skip counts in the envelope evidence.
   - No report, or a timeout: `check.oracle-failed` (error) with the tool's first sanitised line, `retryable` on a timeout.
   - `summary`: `tool_version`, `sheets`, `violations`, `by_type`, `by_severity`, `excluded`, `ignored_checks`, `types` (code to raw type), `tool_writes`.
   - Evidence: `ErcOutcome.evidence`, `KICAD-VERIFIED` only once `H-K-ERC-JSON`, `H-K-ERC-POS` and `H-K-ERC-COPYSET` are; `UNVERIFIED` without a report.

8. **ERC findings as issues.** `checks/erc_json.py::finding_issues(report, *, oracle) -> tuple[Issue, ...]`: one issue per violation.
   - Code `f"{oracle}.erc.{suffix}"`, with the suffix rule of `drc_json.type_code` (moved to a shared helper `checks.codes.type_suffix`); the raw type is kept in `summary.types`.
   - Severity: `info` when `excluded`, else `error` for `error`, `warning` for `warning`, and `error` for any other value.
   - `where`: the items' `where`, or `<sheet>@<x>,<y>` in millimetres for an item without one, joined with `, `.
   - Message `<type>: <description>`, with the temporary folder and the home directory replaced as for DRC.

9. **Parity.** `KicadCli.drc(…, schematic_parity=False)` adds `--schematic-parity` when true; `KicadOracle.drc` passes true in every run when the project set holds `<stem>.kicad_sch`.
   - `drc_json.finding_issues` maps each parity entry to `<oracle>.drc.<type>` like a violation; `summary` gains `parity` (count) and `parity_judged`.
   - When the flag was passed and the tool could not load the schematic (probe `drc-parity-unloadable` records how each major says so), the stage gives `<oracle>.drc.parity-unchecked` (warning) and `parity_judged` is false. `parity-unchecked` joins `RESERVED_SUFFIXES`.
   - The canary adds tracks and nets, no footprint, so parity has nothing to say about it; the probe `drc-parity-canary` confirms that the staged run and the plain run give equal parity entries.

10. **`erc.lite` leaves the KiCad pipeline.** `STAGE_ORDER` holds `erc.kicad` where it held `erc.lite`; `--stages erc.lite` is an unknown stage (exit 2). The hermetic stage list of the docs, of `example_args` and of the missing-tool hint becomes `model.validate,roundtrip`.
    - `checks/erc_lite.py` keeps `ERC_RULES`, `erc_lite`, `erc_stage` and `EVIDENCE` for pipelines of inputs without an ERC oracle; `REMOVE_IN` and `check_removal` are deleted, with their test. The codes `erc.lite.*` stay in `ISSUE_CODES`.
    - Until c0044 lands, nothing in `src/` calls `erc_stage`. The module is kept because a proposed change builds on it; Open Questions asks the maintainer whether to delete it instead.
    - Rejected: one stage `erc` with two engines. A stage whose evidence is sometimes `INFERRED` and sometimes `KICAD-VERIFIED` under one name hides which verdict the reader got.
    - Rejected: keeping `erc.lite` as a tool-free fallback for built projects. Two ERC verdicts for one project disagree by design (three rules against KiCad's full set), and the plan removes it.

11. **RT2 for schematics.** `KicadOracle.rt2_erc(project) -> ErcRt2Outcome(before, after, tool_version, outcome, returncode, message, evidence, redumped, kept)`: ERC twice on the project, and once on a copy in which every readable sheet file is replaced by `dumps(rebuild_schematic(read_schematic(text)))`.
    - RT2 holds when `after.entries()` equals `before[0].entries()`; it is not judged when the two `before` reports differ (`H-K-ERC-REPEAT`).
    - No normalisation: the re-dump has the tree of the source (c0060's RT0), so both sides are the same format version on every major.
    - It is an oracle method and a corpus test here; `check` gets no schematic round-trip stage, because nothing edits a schematic in place before v0.5b. c0066's `roundtrip` command exposes it.

12. **Pre-flight and exit codes.** `erc.kicad` is in `ORACLE_STAGES`, so the existing pre-flight applies: no tool gives exit 6 (`FEN-6001`) before any stage. A schematic the tool cannot load is the stage's `check.oracle-failed`, not a pre-flight error: the board may still be judged.

13. **Determinism.** The output holds no report date, no temporary path and no absolute path; issues are sorted as in every stage; `by_type`, `by_severity`, `ignored_checks` and `tool_writes` are sorted.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/base.py` (extended) | `ErcItem`, `ErcViolation`, `ErcReport` (`entries()`, `of_type`), `ErcOutcome`, `ErcRt2Outcome`, `ErcOracle`; `DrcOutcome.parity_judged` |
| `src/fenolite/backends/kicad/erc.py` (new) | `read_erc_report(text, *, file="", major=None, issues=None) -> ErcReport`; `REQUIRED_KEYS`; `POSITION_SCALE`; `item_locations(trees, project) -> Mapping[tuple[str, str], str]`; `EVIDENCE` |
| `src/fenolite/backends/kicad/cli.py` (extended) | `KicadCli.erc(schematic, *, files=None, env=None) -> ErcRun`; `KicadCli.drc(…, schematic_parity=False)` |
| `src/fenolite/backends/kicad/projectset.py` (extended) | schematic files in `project_set`; `SYMBOL_TABLE = "sym-lib-table"`; `SCHEMATIC_WORKSHEET_POINTER` |
| `src/fenolite/backends/kicad/oracle.py` (extended) | `KicadOracle.erc(project) -> ErcOutcome`; `KicadOracle.rt2_erc(project) -> ErcRt2Outcome`; the parity flag in `drc` |
| `src/fenolite/checks/erc.py`, `erc_json.py` (new) | `erc_stage(oracle, project) -> StageResult`; `finding_issues(report, *, oracle) -> tuple[Issue, ...]` |
| `src/fenolite/checks/stages.py`, `codes.py`, `drc.py`, `drc_json.py` (extended) | `erc.kicad` in `STAGE_ORDER` and `ORACLE_STAGES`; skip reason `no-schematic`; `type_suffix`; parity mapping and summary keys |
| `src/fenolite/checks/erc_lite.py` (reduced) | without `REMOVE_IN` and `check_removal` |
| `src/fenolite/cli/cmd_check.py` (extended) | the oracle for `erc.kicad`; `example_args` with `model.validate,roundtrip` |
| `tests/_fakecli.py` (extended) | `sch erc` and `--schematic-parity` handlers; `erc_report` and `parity` arguments |
| `tests/unit/backends/kicad/test_erc.py`, `tests/unit/checks/test_erc_stage.py`, `test_erc_json.py` (new); `test_projectset.py`, `test_oracle.py`, `test_drc_json.py`, `test_drc_stage.py`, `test_stages.py`, `tests/unit/cli/test_check_cmd.py` (extended) | hermetic |
| `tests/data/kicad/erc/report_9.json`, `report_10.json` (new, authored) | authored reports in the shape of each major |
| `tests/kicad/check/_erccases.py`, `test_erc_facts.py`, `test_erc_oracle.py`, `test_parity.py` (new); `tests/kicad/schematic/test_corpus_rt2.py` (new) | oracle, both majors |
| `docs/formats/kicad/erc.md` (new); `docs/cli-contract.md`, `docs/evidence/kicad-check.md`, `docs/dsl.md`, `docs/formats/kicad/cli.md` (extended) | fact table; stages, codes and the copy set; probe results |

## Sources registered by this change

| id | URL | used for |
|---|---|---|
| S-0330 | https://gitlab.com/kicad/code/kicad/-/raw/10.0.6/resources/schemas/erc.v1.json | key names and required keys of the ERC report at 10.0.6, `ignored_checks` included; not vendored |
| S-0331 | https://gitlab.com/kicad/code/kicad/-/raw/9.0.9.1/resources/schemas/erc.v1.json | the same at 9.0.9.1: no `ignored_checks` |

Rows of other changes cited here: S-0020 (observed `kicad-cli` behaviour), S-0022 and S-0037 (`sch erc`, `pcb drc --schematic-parity`), S-0046 (the ERC checks of the schematic editor), S-0055 and S-0056 (the DRC report schema, for the shape of parity entries). Task 1.1 widens S-0020, S-0022, S-0037 and S-0046. S-0332 to S-0334 stay unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-ERC-JSON | `sch erc --format json --severity-all` writes a report with the keys of Decision 4 and exits 0 when the schematic loads; it writes none and exits 3 when it does not (S-0330, S-0331, S-0020) | `tests/kicad/check/test_erc_facts.py::test_report_shape` | on 9.0.9 and 10.0.6: probes `erc-report-keys` = `equal`, `erc-ignored-checks` = `present` on 10 and `absent` on 9, `erc-unloadable` = `absent` (no report) with exit 3 |
| H-K-ERC-POS | An item's `pos` is its sheet position in the report's unit divided by 100 (S-0020) | `::test_positions` | on both majors: for five items of known position, `read_erc_report` gives the sheet position in nm; probe `erc-position-scale` = `equal` |
| H-K-ERC-TYPES | The five controls give `pin_not_connected`, `pin_not_driven`, `power_pin_not_driven`, `lib_symbol_issues` and the single-pin label warning of each major, and each follows the project's `erc.rule_severities` (S-0046, S-0020) | `::test_types` | on both majors: probes `erc-type-<type>` = `present`; with the key set to `ignore`, `erc-type-<type>-ignored` = `absent`; with `warning`, the severity is `warning` |
| H-K-ERC-COPYSET | ERC on the copy set gives the violations of ERC on a copy of the whole project folder | `tests/kicad/check/test_erc_oracle.py::test_copy_set` | on both majors, for the built blink, the authored hierarchy and three corpus projects: equal `entries()`; probe `erc-copyset` = `equal` |
| H-K-ERC-REPEAT | Two ERC runs on one project give equal `entries()` | `tests/kicad/schematic/test_corpus_rt2.py` | on every project of the run; a project whose runs differ is named and not judged |
| H-K-ERC-RT2 | ERC gives equal `entries()` for a project and for Fenolite's re-dump of its sheets | `tests/kicad/schematic/test_corpus_rt2.py` | on major 10: every corpus project whose sheets are all readable; on major 9: those of tag 9.0.9.1 at format `20250114` or older; no failure, and the projects of the acceptance list (c0060) are all judged |
| H-K-PARITY-RUN | `pcb drc --schematic-parity` fills `schematic_parity`; without the flag the list is empty; the canary does not change it (S-0022, S-0037, S-0020) | `tests/kicad/check/test_parity.py` | on both majors: probes `drc-parity-flag` = `present`, `drc-parity-noflag` = `absent`, `drc-parity-canary` = `equal`; `drc-parity-unloadable` records what each major writes |

Ids used without changing their level: `H-K-CHECK-ERC`, `H-K-CHECK-COPYSET` (proved again with a schematic present), `H-K-PRO-PRL`, `H-K-DRC-JSON`, `H-K-SCH-PARITY`, `H-K-SCH-RT1`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| ERC report reading | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-ERC-JSON`, `H-K-ERC-POS` | `test_erc_facts.py` |
| `erc.kicad` stage | the oracle's level; `H-K-ERC-COPYSET` | `test_erc_oracle.py` |
| Types and severities | KICAD-VERIFIED per major, `H-K-ERC-TYPES` | `test_erc_facts.py::test_types` |
| Parity findings | KICAD-VERIFIED (9.0.x, 10.0.x), `H-K-PARITY-RUN` | `test_parity.py` |
| RT2 on schematics | KICAD-VERIFIED where judged, `H-K-ERC-REPEAT`, `H-K-ERC-RT2` | `test_corpus_rt2.py` |
| Issue mapping, stage order, skips | mechanical | unit tests |
| The three rules | INFERRED, `H-K-CHECK-ERC` | `test_erc_lite.py` |

`erc.EVIDENCE` starts `INFERRED` (`H-K-ERC-JSON`, `H-K-ERC-POS`, `H-K-ERC-COPYSET`) and is raised only when the three are `KICAD-VERIFIED (9.0.x, 10.0.x)`.

## Budget (8.5 days)

| work | days |
|---|---|
| registers, fact rows | 0.5 |
| probes on both majors | 1.25 |
| runner, neutral types, report reader | 1.0 |
| copy set | 0.75 |
| oracle and item locations | 1.0 |
| stage, issue mapping, codes | 1.0 |
| parity | 0.75 |
| `erc.lite` out of the pipeline, texts and tests | 0.75 |
| RT2 oracle and corpus run | 1.0 |
| docs, closing | 0.5 |
| **total** | **8.5** |

Cut order: (1) RT2 on corpus projects outside the acceptance list; (2) `REF-PIN` locations (positions stay); (3) `drc-parity-unloadable` and the `parity-unchecked` code. Not optional: the stage on both majors, parity in the DRC run, `erc.lite` out of `STAGE_ORDER`, RT2 on the acceptance list.

## Risks / Trade-offs

- [A native project relies on global symbol libraries] → `lib_symbol_issues` warnings from the isolated tool; documented, and never errors by KiCad's defaults.
- [ERC of a large hierarchy is slow] → the stage has the command's timeout; the corpus test is marked `slow`.
- [A later KiCad changes the position scale] → `POSITION_SCALE` is per major and proved by a probe; an unknown major leaves positions unscaled and says so.
- [`check` runs one more tool call by default] → `--stages` selects; the measured time of the stage on the examples is written in `docs/evidence/kicad-check.md`.
- [Parity warnings appear on native projects that passed before] → they are KiCad's own findings, warnings by its defaults; the exit code changes only for projects that set them to error.
- [c0044 modifies two of the same requirements] → Migration Plan.
- [Tests that pin `erc.lite` as a stage] → listed by `grep -rl "erc.lite" tests docs src` at task 6.1 and updated in one commit.

## Migration Plan

- `--stages erc.lite` becomes a usage error; the hint of the missing-tool error and the docs name `model.validate,roundtrip`. `agent/SKILL.md` and `README.md`, if they exist then, are updated in the same commit.
- `check` on a project with a schematic reports ERC and parity findings it did not report before.
- The MODIFIED requirements of `verification-loop` are "Check command input", "Check stages and statuses", "Evidence per check stage", "Model validation stage", "ERC lite stage", "DRC stage and the rules canary", "Inputs Fenolite cannot read", "Check exit codes", "Check output is deterministic", "Stages added for findings and round trips" and "DRC findings as issues"; those of `kicad-oracle` and `backend-protocol` are "Check project copy set" and "Oracle protocol". Each delta was generated from the living text with exact replacements.
- The MODIFIED requirements are written against the living text of 2026-10-05, which holds c0051's text of "Check output is deterministic" (archived on 2026-10-04; the delta was generated again on it). c0044 (MODIFIED "Check command input" and "ERC lite stage") touches two of them: whichever change is implemented later re-bases its delta on the text the earlier one left, at its first task.
- After archiving, the Purpose line of the living `verification-loop` spec is corrected by hand (it names "ERC lite").
- Rollback: put `erc.lite` back in `STAGE_ORDER` and take `erc.kicad` out; the runner, the reader and the copy set can stay.

## Open Questions

- **Maintainer: delete `checks/erc_lite.py` outright?** Default: keep the three rules as a function, because c0044 builds on them; delete if c0044 is dropped.
- **Should `erc.kicad` warn when a built project has no schematic (`--schematic skip`)?** Default: the stage is skipped with `no-schematic` and says nothing more.
- **Should a native project's `lib_symbol_issues` be demoted to info?** Default: no; Fenolite reports KiCad's severity.
- **A `roundtrip.rt2` stage for schematics in `check`.** Default: no (Decision 11).
