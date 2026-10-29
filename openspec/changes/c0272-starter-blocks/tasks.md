## 0. Entry check

- [ ] 0.1 Read `openspec list`, the living specs this change touches (`package-layering`, `cli-contract`, `verification-loop`) and the changes it builds on (c0252, c0253, c0254, c0268, c0269, c0270, c0271). Write under this task, with the date and the base commit:
  - the final names of `@block`, `param`, `b.schematic`, `stimulus`, `b.layout(reuse=...)` and `fenolite blocks capture`;
  - c0253's expectation functions and the rating keys `power`, `voltage` and `current` of c0248's records;
  - c0254's generator signatures, the module of `PI` (the π enclosure) and of the I2C mode constants, and whether a public `i2c_mode_limits(mode, bus_capacitance)` exists (if not, task 1.4 adds it over the same table, one formula and two callers);
  - c0254's shipped families: the resistor family of E96 1 % and E24, and a capacitor family of ± 10 % with a voltage rating, in case 0603 (the worked numbers of `design.md` assume them; recompute each scenario with c0254's solver and update the numbers before code if a family differs);
  - c0254's registered id of UM10204, and the next free `S-` numbers;
  - where c0268 puts its catalog code, so that the layering row of `specs/package-layering/` names only the block modules.

  Proof: `openspec validate c0272-starter-blocks --strict`; `make check-fast`.
- [ ] 0.2 Register the sources of design decision 8 in `docs/evidence/sources.md` (licence, what is used, "read for facts, nothing copied"), and replace the placeholders `S-DIV`, `S-JOULE`, `S-RC`, `S-LED`, `S-INTERVAL`, `S-TVS` in `design.md` with the ids. Proof: `uv run pytest tests/unit/test_provenance.py -q`.

## 1. The five blocks

- [ ] 1.1 `fenolite.blocks` package, `__init__`, and the import-graph row (scenario "Blocks stay above the DSL"). Proof: `uv run pytest tests/unit/test_import_graph.py -q`.
- [ ] 1.2 `divider.py` with its usage example, tests and golden file (scenarios "Default divider", "Unreachable output", "Two dividers, no collision"). Proof: `uv run pytest src/fenolite/blocks/tests/test_voltage_divider.py -q`; `uv run fenolite blocks test Fenolite:voltage_divider --json`.
- [ ] 1.3 `rc.py` with its usage example, tests and golden file (scenarios "Default filter", "A window narrower than the capacitor"). Proof: `uv run pytest src/fenolite/blocks/tests/test_rc_lowpass.py -q`; `uv run fenolite blocks test Fenolite:rc_lowpass --json`.
- [ ] 1.4 `led.py` with its usage example, tests and golden file (scenarios "Default indicator", "A pin that cannot drive it", "No forward voltage"). Proof: `uv run pytest src/fenolite/blocks/tests/test_led_indicator.py -q`; `uv run fenolite blocks test Fenolite:led_indicator --json`.
- [ ] 1.5 `i2c.py` with its usage example, tests and golden file (scenarios "Value inside the window for every mode", "Two buses"). Proof: `uv run pytest src/fenolite/blocks/tests/test_i2c_pullups.py -q`; `uv run fenolite blocks test Fenolite:i2c_pullups --json`.
- [ ] 1.6 `circuit.pullup-parallel` in `checks/circuit/`, `checks.codes`, `explain.toml` and `docs/cli-contract.md` (scenario "Two pull-up sets on one bus"). Proof: `uv run pytest tests/unit/checks/circuit/test_pullup_parallel.py tests/unit/cli/test_explain_cmd.py -q`.
- [ ] 1.7 `protect.py` with its usage example (an `Example:` device record authored for it, `UNVERIFIED`, its numbers marked illustrative), tests and golden file (scenarios "Injected current limited by the series resistor", "Clamp above the downstream maximum"). Proof: `uv run pytest src/fenolite/blocks/tests/test_protected_input.py -q`; `uv run fenolite blocks test Fenolite:protected_input --json`.
- [ ] 1.8 `H-G-STARTER-ENCLOSURE`: one property test per block evaluating every corner exactly against the judged ranges; register the hypothesis. Proof: `uv run pytest tests/unit/blocks/test_starter_enclosure.py -q`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.

## 2. Layouts

- [ ] 2.1 Lay out each usage board by hand in KiCad (bench style: every port to the connector), capture each with `fenolite blocks capture ... --confirm`, commit the five layouts, and switch each body to `b.layout(reuse=..., copper=True)`; regenerate the golden files under one `--golden` plan (scenario "Layout properties"). Proof: `uv run pytest tests/unit/blocks/test_starter_layouts.py -q`; `uv run fenolite blocks test --json`.
- [ ] 2.2 KiCad: usage boards of the five blocks for targets 9 and 10 in `tests/kicad/blocks/` (read-back and DRC, c0270 and c0271). Proof: `uv run pytest tests/kicad/blocks` in the KiCad jobs on the pushed head.

## 3. Records, docs and guide

- [ ] 3.1 Records complete: parameter metadata (c0268's `param`, `REQUIRED` for `protection`, `clamp` and `abs_max`), port docs, sources, and the five rows of the blocks' `VERSIONS.toml` (scenarios "The five blocks are listed", "The starter library passes its own tests", "Sources registered"). Proof: `uv run pytest tests/unit/blocks/test_starter.py tests/unit/blocks/test_versions.py tests/unit/test_provenance.py -q`.
- [ ] 3.2 The expectations, usage and layout sections of c0268's `tools/gen_block_docs.py`, and `docs/blocks/` (index and five pages), linked from `docs/dsl.md` (scenario "Pages up to date"). Proof: `uv run pytest tests/unit/blocks/test_block_docs.py tests/consistency -q`; `uv run python tools/gen_block_docs.py --check`.
- [ ] 3.3 Agent guide: a tested line for `fenolite.blocks` on `design-script` (the five names and `design.use`), then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
- [ ] 3.4 Write the list of later blocks (decision 10) into `docs/blocks/index.md` under "Later". Proof: `uv run python tools/gen_block_docs.py --check`.

## 4. Closing

- [ ] 4.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch (unit and KiCad jobs). Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 4.2 Evidence: record the measurements of `H-G-STARTER-ENCLOSURE` in `docs/hypotheses.md`, check that each record's evidence is the lowest of its sources, and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 4.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.
