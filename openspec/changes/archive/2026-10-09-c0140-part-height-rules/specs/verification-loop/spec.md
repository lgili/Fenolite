## ADDED Requirements

### Requirement: Height limits in the placement stage
The stage `placement.rules` of "Placement rules stage" SHALL also judge the height limits of a built project, in both check pipelines, in addition to what that requirement says.
- **What runs.** On a built project whose `rules_of(model)` holds a height limit, the stage MUST run `judge_heights` ("Height limits judged", capability `placement`) with those limits, `heights_of(design, model)` and `extents` from `frame.placed_extents`, which MUST be called only then. On native input, and on a built project without a limit, nothing of this requirement runs and the stage is as "Placement rules stage" leaves it.
- **Summary.** `summary.rules` MUST gain the family `height` with the counts of `judge_heights`; without a limit the family is absent.
- **Status and evidence.** An issue of severity `error` gives the status `errors`, so a part above a limit of severity `error` makes `check` exit 5. A judged limit counts as a judged rule for the evidence rule of "Placement rules stage".
- **Both backends.** On a KiCad project the heights come from the bodies of the `.fenolite/` model; on Altium documents from the bodies of the PCB reading, and for a footprint that holds none there, from the stored model ("Height limits judged"). A part under a limit without a body in either MUST give `placement.height-unknown`, never a pass. The areas are those of the board being judged: a PCB reading that holds no area of the limit's name gives `placement.rule-unresolved` for the limit.
- The stage stays read-only, deterministic and without a subprocess.

#### Scenario: A part above a limit fails the check
- **GIVEN** the blink built with `R1` created with `height=mm(9)`, `design.rule_area("LID", <a square over R1>, layers=("F.Cu",))` and `design.height_limit("LID", max=mm(5))`; no `kicad-cli` on `PATH`
- **WHEN** `uv run pytest tests/unit/checks/test_placement_stage.py -k height` runs `fenolite check <dir> --stages placement.rules --json`
- **THEN** the exit code is 5, no subprocess ran, the issues hold one `placement.too-tall` error with `where == "R1"`, and `summary.rules.height` is `{"judged": 1, "failed": 1, "unknown": 0}`

#### Scenario: No limit, no extents
- **GIVEN** the blink built with `R1` created with `height=mm(9)` and no limit, and a validator whose `placed_extents` raises
- **WHEN** the stage runs
- **THEN** it has status `ok`, `summary.rules` holds no `height`, and `placed_extents` was not called

#### Scenario: A limit on a built Altium project
- **GIVEN** the routed blink with `R1` created with `height=mm(9)`, the area `LID` over `R1` and `design.height_limit("LID", max=mm(5))`, built with `--target altium --confirm`
- **WHEN** `uv run pytest tests/unit/cli/test_check_altium.py -k height` runs `fenolite check <dir> --stages placement.rules --json`
- **THEN** the issues hold one `placement.rule-unresolved` error with `where == "LID"`, no `placement.too-tall` and no `placement.height-unknown`, `summary.rules.height` is `{"judged": 0, "failed": 0, "unknown": 0}`, and the exit code is 5: the Altium reader models no keep-out and the keep-out record has no key for a name (`docs/altium.md`), so the PCB reading holds no area named `LID`; the document holds no body for `R1` either, and the stored board of an Altium build holds only written bodies

### Requirement: Height limit issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities ("Check issue codes"), beside those of "Placement stage issue codes", and `docs/cli-contract.md` MUST document each. `place` and the placement guard of `build` emit the same codes, each with a severity no higher than `warning`. `src/fenolite/cli/data/explain.toml` MUST hold one table for each (`cli-contract`, "Explain command").

| code | severity | when |
|---|---|---|
| `placement.too-tall` | error, warning | a part under a height-limited area is taller than the limit; the limit sets the severity |
| `placement.height-unknown` | warning | a part under a height-limited area has no known height |

A height limit whose area the board does not hold gives `placement.rule-unresolved` of "Placement stage issue codes".

#### Scenario: Height literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** `placement.too-tall` and `placement.height-unknown` are keys of `ISSUE_CODES` with the severities of this table

#### Scenario: Height codes documented and explained
- **WHEN** `uv run pytest tests/consistency tests/unit/cli/test_explain_cmd.py` runs, and then `uv run fenolite explain placement.too-tall --json`
- **THEN** both codes appear in `docs/cli-contract.md`, the explain test passes with a table for each, and the command exits 0 with a non-empty `result.meaning` and `result.fix`
