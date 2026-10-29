## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`design-dsl`, `design-model`, `fenolite-component-catalog`, `verification-loop`) and the state of c0246, c0247, c0248, c0251 and c0253. Write under this task the date, the base commit, and:
  - c0246's `Range` and `ValueRange`, and its canonical text;
  - c0247's `pull_up(target, rail, *resistors)` and the targets it accepts;
  - how c0248 brings device data to a `Part` (the source of the port tables), and its evidence rules;
  - that c0251's tasks 1 to 3 (ports, port nets, model `Port`) are done;
  - whether c0253 has already created a `circuit.*` stage. If it has, add to it instead of creating `circuit.rules`;
  - which open change holds a delta of "Interfaces in the DSL" or "Interface checks in a build". If one was archived, regenerate the MODIFIED blocks from the living text;
  - whether a stage now stands between `model.validate` and `erc.kicad`;
  - the maintainer's answers to the open questions of `design.md`.

  Proof: `npx -y @fission-ai/openspec validate c0252-parametric-interfaces --strict`; `make check-fast`.

## 1. Model

- [ ] 1.1 Add `params`, `reference` and `shared` to the model `Interface`, and `params`, `reference` and `share` to `Port`. Add the kinds `ground` and `logic` and the model-side parameter table, regenerate the schemas, and update `docs/design-model.md` (scenarios "Parameters round trip", "Older circuit files keep their bytes", "Unknown param refused"). Proof: `uv run pytest tests/unit/model/test_circuit.py -k "param or kind" -q`; `uv run python tools/gen_schemas.py --check`.

## 2. Interfaces in the DSL

- [ ] 2.1 Add `dsl/rails.py` with `Rail` (`Power = Rail`), `Ground`, `Logic`, `PARAMETERS` and the main members; add `Design.rail` and `Design.ground`, and the re-exports (scenarios "Power is Rail", "Rail with a voltage", "Wrong unit refused", "Logic with a reference rail", "Rail in one call", "Current on a design rail refused"; every existing test of `tests/unit/dsl/test_interfaces*.py` keeps passing). Proof: `uv run pytest tests/unit/dsl/test_rails.py tests/unit/dsl/test_interfaces.py tests/unit/dsl/test_interfaces_typed.py -q`.
- [ ] 2.2 Add `reference=` to the buses and `pullup=` to `I2C`, and port parameters through c0251's `port(...)` and `PortHandle.set` (scenarios "I2C with a reference and a pull-up range", "Source port of a block"). Proof: `uv run pytest tests/unit/dsl/test_rails.py -k "reference or port" -q`.
- [ ] 2.3 Add net-like interfaces, the interface form of `connect`, the compatibility table and UART crossing (scenarios "Rail joined to a pin", "Two I2C ports", "UART ports cross", "Ground on a rail refused"). Proof: `uv run pytest tests/unit/dsl/test_interface_connect.py tests/unit/dsl/test_connect.py -q`.

## 3. Device ports

- [ ] 3.1 Define c0248's reserved key `interfaces` (`[[interfaces]]` tables) in the device record loader, with the refusals of decision 5 (scenarios "Valid ports load", "Bad ports refused" of "Interface ports of a device" and "Refused device interfaces"). Document them in `docs/catalog/README.md`. Proof: `uv run pytest tests/unit/catalog/test_device_ports.py -q`.
- [ ] 3.2 Add `Part.port` and attribute access, port nets owned by the component path, and model `Port`s from device ports (scenarios "Rail joined to two device ports", "Device port recorded"). Proof: `uv run pytest tests/unit/dsl/test_device_ports.py -q`.
- [ ] 3.3 Widen c0247's `pull_up` to `i2c` ports and `Logic` (scenario "One call, two resistors"), and the power-port target of `build.i2c-pullup-missing` (scenario "Pull-up to a device power port"; the existing "Missing pull-up" keeps passing). Proof: `uv run pytest tests/unit/dsl/test_rails.py -k pull_up tests/unit/lens/test_interface_checks.py -q`.

## 4. Checks

- [ ] 4.1 Add `checks/circuit/rails.py`: `circuit_issues` with the rail grouping, hiding, alias and sum rules, and the eight codes in `checks.codes.ISSUE_CODES`, `docs/cli-contract.md` and `explain.toml` (scenarios "Sensor on a 5 V rail", "Over budget", "Two regulators on one rail", "No voltage to judge against", "3.3 V output into a 1.8 V input", "Same reference passes", "Pulled up to the wrong rail", "VDD and VDDA split"). Proof: `uv run pytest tests/unit/checks/circuit/test_rails.py -q`; `uv run pytest tests/unit/checks tests/unit/test_codes.py -k codes -q`.
- [ ] 4.2 Add the stage `circuit.rules` to `checks/stages.py` (`STAGE_ORDER` and `DOCUMENT_STAGES`) and `cmd_check`, or add the rail checks to it if c0253 created it, with the skip reason `no-parameters` (scenario "A board without parameters is unchanged"). Proof: `uv run pytest tests/unit/checks/test_circuit_stage.py -k "skip or order" -q`.
- [ ] 4.3 Make `cmd_build` add `circuit_issues` to the build envelope, with errors stopping the write unless waived (scenario "Over-budget rail stops the build"). Proof: `uv run pytest tests/unit/cli/test_build_circuit.py -q`.

## 5. Example, docs and guide

- [ ] 5.1 Add `examples/sensor_rails/` (CC0, illustrative devices authored for Fenolite in the test catalog): a 12 V input, the `buck` block of c0251 promising 3.3 V at 1 A, an MCU and an I2C sensor, in a `good` and a `bad` variant. The bad variant overloads `3V3` and pulls the bus up to the wrong rail. Add the stage tests on both (scenarios "The good variant passes", "Over budget"), and the read-back of the good variant through `kicad-cli` in the KiCad CI job. Proof: `uv run pytest tests/unit/checks/test_circuit_stage.py -q` locally; the read-back test in CI (task 6.2).
- [ ] 5.2 `docs/dsl.md`: sections "Rails, grounds and logic", "Interface parameters" (with the alias, sum, bound and link table), "Connecting interfaces" and "Device ports". `docs/cli-contract.md`: the stage and its codes. Proof: `uv run pytest tests/consistency -q`.
- [ ] 5.3 Agent guide (AGENTS.md rule 6): tested lines for `Rail`, `Ground`, `Logic`, `Design.rail`, `Design.ground` and the interface form of `connect` on `design-script`; the stage and its codes on `checks`; rails and the current budget on `board-power`. Regenerate the generated pages. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.

## 6. Changelog and CI

- [ ] 6.1 `CHANGELOG.md`: one entry under `## [Unreleased]`. This waits until `dev` is at `0.7.0.dev0`: at `0.6.0` the v0.6 guard requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit/test_release_record_v06.py tests/consistency -q` on the `0.7.0.dev0` base.
- [ ] 6.2 Push the batch to the working branch and confirm that the required unit and KiCad jobs pass on that exact commit. Run only `make check-fast` and the focused tests locally (AGENTS.md, workflow 4). Proof: the run of the commit on GitHub CI is green; `make check-fast` passes locally.
