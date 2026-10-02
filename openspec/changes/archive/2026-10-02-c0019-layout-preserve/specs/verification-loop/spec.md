## MODIFIED Requirements

### Requirement: Model validation stage
`checks.validate.validate_stage(design, *, built, evidence) -> StageResult` SHALL report the structural findings of the model under check.
- Native input MUST use `Validation.read.design`. Built input MUST use the `.fenolite/` model.
- The stage MUST report the `model.*` findings of `Design.validate()` with their severities.
- It MUST report `check.footprint-unresolved` (error, `where` = the reference) for each component that is not DNP and has an empty `lib_footprint_ref` or no footprint instance.
- On built input it MUST report `check.symbol-unresolved` (error, `where` = the reference) for each component with an empty `lib_symbol_ref`, DNP or not, whose `properties` hold a `fenolite.path` key.
- A component of built input whose `properties` hold no `fenolite.path` key is board-only: a footprint added in KiCad, which a rebuild keeps with the component that `read_board` gives it and no symbol (`layout-lens`, "Orphan and board-only footprints"). It MUST NOT be reported as `check.symbol-unresolved`; every other rule of this stage applies to it.
- A `.fenolite/` folder that `load_dir` cannot load MUST give one `check.cache-unreadable` warning, and `model.validate` and `erc.lite` MUST be skipped with reason `cache-unreadable`. The other stages MUST still run.

#### Scenario: Clean built project
- **GIVEN** the authored built project, in which every component has a `lib_symbol_ref` and a placed footprint
- **WHEN** `fenolite check <project> --stages model.validate --json` runs
- **THEN** the stage has status `ok` and level `INFERRED`, and the exit code is 0

#### Scenario: Unresolved footprint and symbol
- **GIVEN** a built model with one component whose `lib_footprint_ref` and `lib_symbol_ref` are empty and whose `properties` hold a `fenolite.path` key, and one DNP component whose `lib_symbol_ref` is set and that has no footprint instance
- **WHEN** `uv run pytest tests/unit/checks -k validate_stage` runs the stage
- **THEN** it reports one `check.footprint-unresolved` and one `check.symbol-unresolved` for the first component, nothing for the DNP one, and status `errors`

#### Scenario: Board-only component not asked for a symbol
- **GIVEN** a built model whose component `H1` has an empty `lib_symbol_ref`, no `fenolite.path` key in its `properties`, a `lib_footprint_ref` and a placed footprint
- **WHEN** `uv run pytest tests/unit/checks -k validate_stage` runs the stage
- **THEN** it reports neither `check.symbol-unresolved` nor `check.footprint-unresolved` for `H1`

#### Scenario: Rebuilt blink with a mounting hole added in KiCad
- **GIVEN** a confirmed target-10 blink build in `B` whose board gets, by token edit, a footprint `H1` that stands in for a mounting hole added in KiCad (made from `Mini_R_0603`, without a `fenolite.path` property, pad `1` on `GND` and pad `2` on no net), after which `fenolite build examples/blink_2layer/design.py --out B --confirm` runs again
- **WHEN** `fenolite check B --stages model.validate,erc.lite,roundtrip --json` runs
- **THEN** the exit code is 0, no issue has severity `error`, and no `check.symbol-unresolved` is reported

#### Scenario: Unreadable cache
- **GIVEN** the authored built project whose `.fenolite/board.json` holds `{`
- **WHEN** `fenolite check <project> --stages model.validate,erc.lite,roundtrip --json` runs
- **THEN** the issues hold one `check.cache-unreadable` warning, both model stages are skipped with reason `cache-unreadable`, and `roundtrip` has status `ok`
