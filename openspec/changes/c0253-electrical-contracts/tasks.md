## 0. Entry check

- [ ] 0.1 Read `openspec list`, `AGENTS.md`, `docs/research/circuit-as-code.md` (section 7) and the living specs this change touches (`design-dsl`, `design-model`, `verification-loop`, `cli-contract`, `net-roles`, `board-analyses`, `package-layering`, `agent-guide`). Write under this task, with the date and the base commit:
  - what c0246, c0248, c0251 and c0252 landed, and whether each item below exists as `design.md` reads it (if one differs, record which decision changes):
    - c0246: `Range`, `between`, `pct()` (`Tolerance`) and `Component.value_range` with its encoding;
    - c0248: `DeviceDef` ratings, `DevicePin.voltage`/`current` with `ground`, the `fenolite.device` and `fenolite.device.sha256` properties, and the unit parsers in `core/units.py`;
    - c0251: the builder `b`;
    - c0252: the stage `circuit.rules`, `circuit_issues(model)`, its skips, its build hook and rule, rail voltage and load sums;
  - c0252's living "Circuit stage" text. The ADDED requirements of `verification-loop` here extend it; if c0252 is not archived yet, record the order of archiving;
  - whether an open change holds a delta of "Requirement tables supplied by the user" (if one was archived, rewrite the MODIFIED block from the living text);
  - the maintainer's answers to the open questions of `design.md`, and to c0252's Open question 1 (build rule).

  Proof: `openspec validate c0253-electrical-contracts --strict --no-interactive`.

## 1. Units and the row type

- [ ] 1.1 Add `parse_temperature`, `parse_temperature_difference` and `parse_area` to `core/units.py`, beside c0248's electrical parsers, and add `celsius` and `kelvin` to `dsl/quantity.py`. Proof: `uv run pytest tests/unit/core/test_units.py tests/unit/dsl/test_quantity.py -q`.
- [ ] 1.2 Add unit keys and `source` to `analysis/requirements.py`, and update `docs/analyses.md`, "The requirements file" (scenarios "Unit keys equal raw keys", "Unit errors", "Source text", and the five scenarios kept from the living text). Proof: `uv run pytest tests/unit/analysis/test_requirements.py tests/unit/analysis/test_facts_page.py -q`.
- [ ] 1.3 Add `core/requirement_table.py`: `RequirementRow`, `Bound`, the four sources, exact number text and canonical order. Proof: `uv run pytest tests/unit/core/test_requirement_table.py -q`.

## 2. Model and DSL

- [ ] 2.1 Add the model objects and `RuleSet.contracts` to `model/rules.py`, regenerate the schemas, and describe them in `docs/design-model.md`:
  - `DeratingRule`, `OperatingRange`, `Expectation`, `RigSupply`, `RigSink` and `ContractSet`;
  - the closed tables `DERATING_KEYS`, `EXPECT_OPS` and `EXPECT_REFS`.

  Scenarios: "Contracts round trip", "Files of an older build", "Refused values". Proof: `uv run pytest tests/unit/model/test_rules.py -k contracts -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 2.2 Add `dsl/contracts.py`:
  - `Design.derating`, `Design.operating`, `Design.expect` and `Design.rig`;
  - `b.expect` on the block builder;
  - `within`, `at_least` and `at_most`;
  - `value_of`, `rating_of`, `voltage_of` and `current_of`;
  - `supply` and `sink`;
  - handles with a refusing `__bool__`, and `to_model` into `RuleSet.contracts`.

  Scenarios: "Contracts are built", "A ratio that is not whole per-mille", "Helpers are exported", "No silent branch", "An unknown rating key", "A literal comparison is refused", "A rig on a net without parts", "Bad ratios". Proof: `uv run pytest tests/unit/dsl/test_contracts.py -q`.
- [ ] 2.3 Run `uv run python tools/gen_agent_guide.py` for the new DSL names, and add them to `docs/dsl.md`, section "Electrical contracts". Proof: `uv run python tools/gen_agent_guide.py --check`; `uv run pytest tests/unit/dsl -k docs -q`.

## 3. The judge

- [ ] 3.1 Turn c0252's `checks/circuit.py` into the package `checks/circuit/` without changing its behaviour. Proof: `uv run pytest tests/unit/checks -k circuit -q`.
- [ ] 3.2 `checks/circuit/values.py`: voltage and current bounds by source order, `circuit.value-conflict`, part classes, and rig elements as rail sources and loads (scenarios "A rig bounds the input", "Unconfirmed roles give nothing", "Two sources disagree", "A stated class wins", "A rig supply beside a regulator"). Proof: `uv run pytest tests/unit/checks/circuit/test_values.py -q`.
- [ ] 3.3 `checks/circuit/ratings.py`: voltage, current, power and temperature rows, the derating policy and its precedence, and the count findings. Scenarios:
  - "Input capacitor without a policy", "Pin rating of a regulator", "Drain to source";
  - "Inductor on a busier rail", "A pull-up is not judged by current";
  - "A bleeder across the input", "A commercial part in a cold box";
  - "The policy tightens the input capacitor", "A part scope wins", "No policy, no derating";
  - "No defaults in the code", "Unknown rows stay quiet".

  Proof: `uv run pytest tests/unit/checks/circuit/test_ratings.py tests/unit/checks/circuit/test_policy.py -q`.
- [ ] 3.4 `checks/circuit/expect.py`: evaluating the expression tree on the model, and the three-valued judgement (scenarios "The divider of a buck", "Judged again after an edit", "A value without a range"). Proof: `uv run pytest tests/unit/checks/circuit/test_expect.py -q`.
- [ ] 3.5 Add the twelve codes to `checks/codes.py` and their `explain.toml` entries (scenario "Codes explained"). Proof: `uv run pytest tests/unit/checks/test_codes.py tests/unit/cli/test_explain_cmd.py -k circuit -q`.

## 4. Stage, commands and table

- [ ] 4.1 Extend the stage `circuit.rules`: contracts judged, `summary.requirements`, `no-parameters` lifted for contracts, devices injected, evidence. Scenarios: "A failing rating gates the check", "Contracts alone run the stage", "A board without a model is unchanged", "A fake mapping", "A device edited after the build", "Deterministic and tool-free", "Layering holds", "An unverified device lowers the stage evidence". Proof: `uv run pytest tests/unit/checks/circuit/test_stage.py tests/unit/checks/test_stages.py tests/unit/test_import_graph.py -q`.
- [ ] 4.2 Make `cmd_check`, `cmd_build` and `cmd_roles` resolve and pass the device records, and make the build report the contract codes through c0252's hook (scenario "Build and check agree"). Proof: `uv run pytest tests/unit/cli/test_build_cmd.py tests/unit/cli/test_check_cmd.py -k circuit -q`.
- [ ] 4.3 Add role rows in `roles/judge.py` and `summary.requirements` of `roles.rules` (scenarios "The bad buck's rows", "Profile and override sources"). Proof: `uv run pytest tests/unit/roles -q`.
- [ ] 4.4 Add `result.requirements` to `fenolite roles --check`, joining the role rows and the circuit rows, with `[[current]]` rows bounding both. Describe it in `docs/cli-contract.md` under the heading `roles` (scenarios "One table for roles and circuit", "A board that Fenolite did not build", "A stated current reaches the circuit rows", "Rows of the bad sensor"). Proof: `uv run pytest tests/unit/cli/test_roles_cmd.py tests/unit/checks/circuit/test_table.py -q`.

## 5. Example and rig exclusion

- [ ] 5.1 Add `examples/circuit/sensor/` (`good.py`, `bad.py`, and `requirements.toml` with unit keys and the authored mark), built on the illustrative devices of c0248 and the buck block of c0251 (scenario "Good and bad sensors"; hypothesis `H-G-CIRCUIT-EXAMPLE`). Proof: `uv run pytest tests/unit/checks/circuit/test_example.py -q`.
- [ ] 5.2 Rig exclusion: build with and without the rig, and compare every output (scenario "Outputs are unchanged by a rig"). Proof: `uv run pytest tests/unit/dsl/test_contracts.py -k rig_outputs -q`.

## 6. Closing

- [ ] 6.1 Docs:
  - write `docs/contracts.md`: values and their sources, part classes, ratings checks, derating (no shipped values, and how to cite your own), expectations, the rig, the requirement table and the codes;
  - link it from `docs/roles.md`, `docs/dsl.md`, `docs/analyses.md` and `docs/index.md`;
  - add a section to `docs/roles.md` on the role rows of the table.

  Proof: `uv run pytest tests/unit/test_docs_links.py tests/consistency -q`.
- [ ] 6.2 Agent guide:
  - put tested lines for `design.derating`, `design.operating`, `design.expect`, `design.rig` and the eleven helper names in a `fenolite-design` block of `board-power`;
  - add `fenolite check --stages circuit.rules` and `fenolite roles --check` with the table on `checks`;
  - add unit keys to the requirements example of `rules`;
  - then run `uv run python tools/gen_agent_guide.py`.

  Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [ ] 6.3 Add the hypothesis `H-G-CIRCUIT-EXAMPLE` to `docs/hypotheses.md` with its measurement. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 6.4 Residue: every authored file carries its authored-for-Fenolite line, and no value, name or table comes from another project or a derating standard. Proof: `make residue`.
- [ ] 6.5 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0` on `dev`: the v0.6 guard requires `[Unreleased]` to be empty while `dev` is at `0.6.0`. Proof: `uv run pytest tests/unit -k changelog -q`.
- [ ] 6.6 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Proof: `make check-fast`, and every required job green on the exact commit.
- [ ] 6.7 Validate the change. Proof: `openspec validate c0253-electrical-contracts --strict --no-interactive`.
