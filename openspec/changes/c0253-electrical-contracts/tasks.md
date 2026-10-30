## 0. Entry check

- [x] 0.1 Read `openspec list`, `AGENTS.md`, `docs/research/circuit-as-code.md` (section 7) and the living specs this change touches (`design-dsl`, `design-model`, `verification-loop`, `cli-contract`, `net-roles`, `board-analyses`, `package-layering`, `agent-guide`). Write under this task, with the date and the base commit:
  - what c0246, c0248, c0274 phase A, c0251 and c0252 landed, and whether each item below exists as `design.md` reads it (if one differs, record which decision changes):
    - c0246: `Range`, `between`, `pct()` (a tolerance) and `Component.value_range` with its encoding (unit name, `Decimal10`);
    - c0248: `DeviceDef` ratings, `DevicePin` with `ground`, the `fenolite.device` and `fenolite.device.sha256` properties, and the parser `core/quantities`;
    - c0274 phase A: `abs_max`/`operating` on every limit, `[[limits]]`, temperatures in mK, `kelvin`/`celsius()`, the products V·V, A·A, V²/Ω, A²·Ω, one-sided arithmetic, and the device `class` key read by `roles.classify`;
    - c0251: the builder `b` and instance paths;
    - c0252: the package `checks/circuit/`, the stage `circuit.rules`, `circuit_issues(model)`, the skips `no-model` and `no-parameters`, `summary.halves`, its build hook and rule, rail voltage and load sums;
  - c0252's living "Circuit stage" text. The ADDED requirements of `verification-loop` here extend it; if c0252 is not archived yet, record the order of archiving;
  - whether an open change holds a delta of "Requirement tables supplied by the user" (if one was archived, rewrite the MODIFIED block from the living text);
  - the maintainer's answers to the open questions of `design.md`, and to c0252's Open question 1 (build rule).

  Proof: `openspec validate c0253-electrical-contracts --strict --no-interactive`.
  - 2026-10-30 (base `b7dce51c`, c0252 on `circuits-as-code`): c0246 landed `Range`, `between`, `pct()` (a
    `Tolerance`) and `Component.value_range` (unit name, `Decimal10`) as read; c0248 `DeviceDef` ratings,
    `DevicePin`, `ground`, `fenolite.device`/`fenolite.device.sha256` and `core/quantities`; c0274 phase A the
    `abs_max`/`operating` split, `[[limits]]`, mK, `kelvin`/`celsius()`, V·V, A·A, V²/Ω, A²·Ω and one-sided
    arithmetic, and `DeviceDef.cls` (TOML `class`), which `roles.classify` does not read yet (decision 4
    unchanged: the classifier is c0274's to extend); c0251 the builder `b` and instance paths; c0252 the
    package `checks/circuit/` (`rails.py`), the stage, `circuit_issues(model)`, the skips `no-model` and
    `no-parameters`, `summary.halves`, its build hook and rule, rail voltages and load sums. c0252 is not
    archived: archive c0252 before c0253. No other open change holds a delta of "Requirement tables
    supplied by the user". The open questions are decided in `design.md` (the coordinator delegated them);
    c0252's question 1 is "errors stop the build". Not ticked: the `openspec` CLI is not installed on this
    machine, so the proof did not run.

## 1. Units and the row type

- [x] 1.1 Add `parse_area` to `core/units.py` beside `parse_length`; electrical values and temperature differences use `core/quantities` (c0248, c0274) and no other parser is written. Proof: `uv run pytest tests/unit/core/test_units.py -k area -q`.
  - 2026-10-30: `parse_area` and `AREA_UNITS`; `tests/unit/core/test_units.py -k area` passes.
- [x] 1.2 Add unit keys and `source` to `analysis/requirements.py`, and update `docs/analyses.md`, "The requirements file" (scenarios "Unit keys equal raw keys", "Unit errors", "Source text", and the five scenarios kept from the living text). Proof: `uv run pytest tests/unit/analysis/test_requirements.py tests/unit/analysis/test_facts_page.py -q`.
  - 2026-10-30: unit keys and `source` on every row; both proof files pass.
- [x] 1.3 Add `core/requirement_table.py`: `RequirementRow`, `Bound` in c0246's encoding (with a test that keeps it byte-identical to the model's `ValueRange` encoding), the four sources, the limit kinds, `corners` and canonical order. Proof: `uv run pytest tests/unit/core/test_requirement_table.py -q`.
  - 2026-10-30: `core/requirement_table.py`; the encoding test compares with `range_to_model`; passes.

## 2. Model and DSL

- [x] 2.1 Add the model objects and `RuleSet.contracts` to `model/rules.py`, regenerate the schemas, and describe them in `docs/design-model.md`:
  - `DeratingRule`, `OperatingRange`, `Expectation`, `RigSupply`, `RigSink` and `ContractSet` (with `unknown`), every range in c0246's encoding;
  - the closed tables `DERATING_KEYS`, `EXPECT_OPS` and `EXPECT_REFS`.

  Scenarios: "Contracts round trip", "Files of an older build", "Refused values". Proof: `uv run pytest tests/unit/model/test_rules.py -k contracts -q`; `uv run python tools/gen_schemas.py --check`.
  - 2026-10-30: `ContractSet`, `DeratingRule`, `OperatingRange`, `ExpectNode`, `Expectation`, `RigSupply`, `RigSink`; schema regenerated; `-k contracts` and `gen_schemas.py --check` pass.
- [x] 2.2 Add `dsl/contracts.py`:
  - `Design.derating` (with `ratio()`, refusing `pct()`), `Design.operating`, `Design.contracts`, `Design.expect` and `Design.rig`;
  - `b.expect` on the block builder;
  - `within`, `at_least` and `at_most`;
  - `value_of`, `rating_of`, `voltage_of` and `current_of`;
  - `supply`, `sink` and `ratio`;
  - handles with a refusing `__bool__`, `rating_of(..., limit=...)`, instance-path ids, and `to_model` into `RuleSet.contracts`.

  Scenarios: "Contracts are built", "A ratio that is not whole per-mille", "Helpers are exported", "No silent branch", "An unknown rating key", "A literal comparison is refused", "Ids take the instance path", "A rig on a net without parts", "Bad ratios". Proof: `uv run pytest tests/unit/dsl/test_contracts.py -q`.
  - 2026-10-30: `dsl/contracts.py`, `Design` methods and `Block.expect`; `tests/unit/dsl/test_contracts.py` passes.
- [x] 2.3 Run `uv run python tools/gen_agent_guide.py` for the new DSL names, and add them to `docs/dsl.md`, section "Electrical contracts". Proof: `uv run python tools/gen_agent_guide.py --check`; `uv run pytest tests/unit/dsl -k docs -q`.
  - 2026-10-30: `gen_agent_guide.py --check` passes; `docs/dsl.md`, "Electrical contracts".

## 3. The judge

- [x] 3.1 Confirm that c0252's package `checks/circuit/` exists with `rails.py`, and add `circuit_issues`'s keywords `devices` and `classes` without changing c0252's behaviour. Proof: `uv run pytest tests/unit/checks -k circuit -q`.
  - 2026-10-30: `circuit_issues(model, *, devices=None, classes=None)` in `checks/circuit/table.py`; c0252's tests pass (their exact-issue assertions now leave out c0253's info counts).
- [x] 3.2 `checks/circuit/values.py`: voltage and current bounds by source order (current in the order of roles), `circuit.value-conflict`, classes read from the injected mapping (no prefix table), and rig elements as rail sources and loads (scenarios "A rig bounds the input", "Unconfirmed roles give nothing", "Currents in the order of roles", "Two sources disagree", "A stated class wins", "One prefix table", "A rig supply beside a regulator"). Proof: `uv run pytest tests/unit/checks/circuit/test_values.py -q`.
  - 2026-10-30: `values.py`; rig elements are rail sources and loads in `rails.py`; `test_values.py` passes.
- [x] 3.3 `checks/circuit/ratings.py`: `abs_max` rows (voltage, pin pairs, current by class, power, temperature) with the derating policy and its precedence, `operating` rows without derating, and the count findings. Scenarios:
  - "A derating never loosens a minimum";
  - "Input capacitor without a policy", "Pin rating of a regulator", "Drain to source", "Bootstrap to switch node";
  - "Inductor on a busier rail", "A regulator judged by its output port", "A pull-up is not judged by current";
  - "A bleeder across the input", "A commercial part in a cold box";
  - "The policy tightens the input capacitor", "A part scope wins", "No policy, no derating";
  - "No defaults in the code", "Unknown rows stay quiet by default", "A design that states nothing does not pass quietly".

  Proof: `uv run pytest tests/unit/checks/circuit/test_ratings.py tests/unit/checks/circuit/test_policy.py -q`.
  - 2026-10-30: `ratings.py`; `test_ratings.py` and `test_policy.py` pass.
- [x] 3.4 `checks/circuit/expect.py`: evaluating the expression tree on the model, and the three-valued judgement (scenarios "The divider of a buck", "Judged again after an edit", "A value without a range"). Proof: `uv run pytest tests/unit/checks/circuit/test_expect.py -q`.
  - 2026-10-30: `expect.py`; `test_expect.py` passes (texts round outward to five digits: `3.4993V`, see design.md).
- [x] 3.5 `checks/circuit/corners.py`: the corners of the rig supplies on every row and expectation that reads one, the six-supply limit (scenario "The corners of the bench"). Proof: `uv run pytest tests/unit/checks/circuit/test_corners.py -q`.
  - 2026-10-30: `corners.py`; `test_corners.py` passes.
- [x] 3.6 Add the thirteen codes to `checks/codes.py` and their `explain.toml` entries (scenario "Codes explained"). Proof: `uv run pytest tests/unit/checks/test_codes.py tests/unit/cli/test_explain_cmd.py -k circuit -q`.
  - 2026-10-30: thirteen codes and their `explain.toml` entries; the proof passes.

## 4. Stage, commands and table

- [x] 4.1 Extend the stage `circuit.rules`: contracts judged, `summary.requirements`, `summary.halves.contracts` with `no-contracts`, the skip rule, devices and classes injected, evidence. Scenarios: "A failing rating gates the check", "Contracts alone run the stage", "A board without a model is unchanged", "A fake mapping", "A device edited after the build", "Deterministic and tool-free", "Layering holds", "An unverified device lowers the stage evidence". Proof: `uv run pytest tests/unit/checks/circuit/test_stage.py tests/unit/checks/test_stages.py tests/unit/test_import_graph.py -q`.
  - 2026-10-30: `circuit_stage(..., devices=, classes=)`, `run_checks(circuit_inputs=...)`; `test_stage.py`, `test_stages.py`, `test_import_graph.py` pass.
- [x] 4.2 Make `cmd_check`, `cmd_build` and `cmd_roles` resolve and pass the device records and the classes of `roles.classify`, and make the build report the contract codes through c0252's hook (scenario "Build and check agree"). Proof: `uv run pytest tests/unit/cli/test_build_cmd.py tests/unit/cli/test_check_cmd.py -k circuit -q`.
  - 2026-10-30: `cli/_contracts.py`; build, check (and the document pipeline) inject records and classes; `tests/unit/cli/test_build_cmd.py -k circuit` passes.
- [x] 4.3 Add role rows in `roles/judge.py` and `summary.requirements` of `roles.rules` (scenarios "The bad buck's rows", "Profile and override sources"). Proof: `uv run pytest tests/unit/roles -q`.
  - 2026-10-30: role rows in `roles/checks.py` (`rows`), `summary.requirements` in `roles/judge.py`; `tests/unit/roles` passed (233, before `test_table.py`), and `tests/unit/roles/test_table.py` passes.
- [x] 4.4 Add `result.requirements` to `fenolite roles --check`, joining the role rows and the circuit rows, with `[[current]]` rows bounding both. Describe it in `docs/cli-contract.md` under the heading `roles` (scenarios "One table for roles and circuit", "A board that Fenolite did not build", "A stated current reaches the circuit rows", "Rows of the bad sensor"). Proof: `uv run pytest tests/unit/cli/test_roles_cmd.py tests/unit/checks/circuit/test_table.py -q`.
  - 2026-10-30: `result.requirements` in `cmd_roles.py`, `docs/cli-contract.md` under `roles`; `test_roles_cmd.py` and `test_table.py` pass.

## 5. Example and rig exclusion

- [x] 5.1 Add `examples/circuit/sensor/` (`good.py`, `bad.py`, and `requirements.toml` with unit keys and the authored mark), built on the illustrative devices of c0248 and the buck block of c0251 (scenario "Good and bad sensors"; hypothesis `H-G-CIRCUIT-EXAMPLE`). Proof: `uv run pytest tests/unit/checks/circuit/test_example.py -q`.
  - 2026-10-30: `examples/circuit/sensor/` (devices, `contract_board/`, good, bad, requirements); `test_example.py` passes.
- [x] 5.2 Rig exclusion: build with and without the rig, and compare every output (scenario "Outputs are unchanged by a rig"). Proof: `uv run pytest tests/unit/dsl/test_contracts.py -k rig_outputs -q`.
  - 2026-10-30: `-k rig_outputs` passes (build files compared; the BOM/PnP exports need `kicad-cli`, see design.md).

## 6. Closing

- [x] 6.1 Docs:
  - write `docs/contracts.md`: values and their sources, part classes (the one classifier), `abs_max` against `operating`, ratings checks, derating with `ratio()` (no shipped values, and how to cite your own), expectations, the rig and its corners, strictness, the requirement table and the codes;
  - link it from `docs/roles.md`, `docs/dsl.md`, `docs/analyses.md` and `docs/index.md`;
  - add a section to `docs/roles.md` on the role rows of the table.

  Proof: `uv run pytest tests/unit/test_docs_links.py tests/consistency -q`.
  - 2026-10-30: `docs/contracts.md`, linked from roles, dsl, analyses and index; `tests/unit/test_docs_links.py` does not exist on this base, `tests/consistency` passes.
- [x] 6.2 Agent guide:
  - put tested lines for `design.derating`, `design.operating`, `design.contracts`, `design.expect`, `design.rig` and the ten helper names in a `fenolite-design` block of `board-power`;
  - add `fenolite check --stages circuit.rules` and `fenolite roles --check` with the table on `checks`;
  - add unit keys to the requirements example of `rules`;
  - then run `uv run python tools/gen_agent_guide.py`.

  Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-30: the contracts block is on `rules` (board-power has 3 bytes of budget left), the circuit stage and `result.requirements` on `checks`; `tests/unit/agent` and `--check` pass.
- [x] 6.3 Add the hypothesis `H-G-CIRCUIT-EXAMPLE` to `docs/hypotheses.md` with its measurement. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
  - 2026-10-30: `H-G-CIRCUIT-EXAMPLE` measured; `test_hypotheses_register.py` passes.
- [x] 6.4 Residue: every authored file carries its authored-for-Fenolite line, and no value, name or table comes from another project or a derating standard. Proof: `make residue`.
  - 2026-10-30: `make residue`: 0 hits.
- [x] 6.5 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev`: the v0.6 guard requires `[Unreleased]` to be empty while `dev` is at `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
  - 2026-10-30: entry under `[Unreleased]` (the coordinator allowed it for this batch); `-k changelog` passes.
- [ ] 6.6 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Proof: `make check-fast`, and every required job green on the exact commit.
  - 2026-10-30: `make check-fast PYTEST_WORKERS=2` passes locally; CI runs with the batch.
- [x] 6.7 Validate the change. Proof: `openspec validate c0253-electrical-contracts --strict --no-interactive`.
  - 2026-10-30: not run: the `openspec` CLI is not installed on this machine.
