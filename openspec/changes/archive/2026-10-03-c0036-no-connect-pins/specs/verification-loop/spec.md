## MODIFIED Requirements

### Requirement: ERC lite stage
`checks.erc_lite` SHALL define `ERC_RULES = ("output-conflict", "power-undriven", "floating-pin")`, `erc_lite(design) -> tuple[Issue, ...]`, `erc_stage(design) -> StageResult`, `EVIDENCE` (`INFERRED`, `H-K-CHECK-ERC`) and `REMOVE_IN = (0, 2)`. The stage MUST run on built input only; on native input it MUST be skipped with reason `native-input`.
- `erc.lite.output-conflict`: a net with two or more member pins whose `etype` is `output` or `power_out`.
- `erc.lite.power-undriven`: a net with a `power_in` member pin and no `power_out` member pin, whose id is not a value of the `members` of any `Interface` with `kind == "power"` (c0011's `Power(hv, lv)`, which acts as a power flag).
- `erc.lite.floating-pin`: a pin whose `etype` is not `no_connect`, that no net lists and that `Circuit.no_connects` does not list (`design-model`, "No-connect marks in the circuit model"), reported once per pin. A mark is matched by `PinRef(<component id>, <pin number>)`, the form the builds store.
- The three rules MUST NOT report a marked pin that a net also lists: that is `model.no-connect-on-net`, a finding of `Design.validate()` and of the `model.validate` stage.
- Pins of components with `dnp == True` MUST be ignored by the three rules.
- Every finding MUST have severity `warning`.
- `check_removal(version: str) -> None` MUST raise `RuntimeError` naming `erc.lite` and `REMOVE_IN` when `version` is at least `REMOVE_IN`. A unit test MUST call it with `fenolite.__version__`, so the suite fails once the package reaches 0.2 and the stage is removed or replaced by `sch erc` (v0.2a).

#### Scenario: One case per rule
- **GIVEN** one authored model per rule and a clean control model
- **WHEN** `uv run pytest tests/unit/checks -k erc_lite` runs
- **THEN** each rule model gives exactly its own warning, and the control gives none

#### Scenario: Power interface drives a net
- **GIVEN** a model whose net `VCC` has one `power_in` pin and no `power_out` pin, and an `Interface(kind="power")` whose `members` name the id of `VCC`
- **WHEN** `erc_lite` runs
- **THEN** it reports no `erc.lite.power-undriven`

#### Scenario: Removal deadline
- **GIVEN** `fenolite.__version__` patched to `0.2.0`, and the live version below `0.2`
- **WHEN** `uv run pytest tests/unit/checks -k remove_in` runs
- **THEN** it passes: `check_removal` raises `RuntimeError` naming `erc.lite` and `REMOVE_IN` for the patched version (`pytest.raises`), and returns `None` for the live version

#### Scenario: Marked pin is not floating
- **GIVEN** a model whose component `U1` has the `input` pins `11`, `12` and `13` on no net, and whose `Circuit.no_connects` holds `PinRef(<U1 id>, "11")` and `PinRef(<U1 id>, "12")`
- **WHEN** `uv run pytest tests/unit/checks -k "erc_lite and no_connect"` runs `erc_lite`
- **THEN** it reports exactly one `erc.lite.floating-pin`, whose `where` is `U1-13`

#### Scenario: Marked pins of a built project
- **GIVEN** a blink variant with `U1` of `Mini:Mini_QFP32_IC` whose supply pins are connected and whose remaining pins are all marked with `no_connect`, built with `--confirm` into `B`
- **WHEN** `fenolite check B --stages erc.lite --json` runs
- **THEN** the exit code is 0 and no `erc.lite.floating-pin` issue names `U1`
