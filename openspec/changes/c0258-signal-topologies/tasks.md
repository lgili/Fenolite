## 0. Entry check

- [ ] 0.1 Read `openspec list` and confirm, with the date and the base commit written under this task: c0256 is archived (subjects, `findings()`), and c0248 (`bridges` in device records), c0252 (interface kinds) and c0246 (ranges) are archived or their parts here are deferred; `STAGE_ORDER` still has `length.rules` with no stage after it before `placement.rules`; `rule_precedence` and "Lowered rules follow priority" are unchanged; whether a probe of the KiCad 10 tuning profile's time-domain keys exists (`H-K-PRO-TIME-DOMAIN`); and the maintainer's answers to the open questions of `design.md`. Proof: `npx -y @fission-ai/openspec validate c0258-signal-topologies --strict`; `uv run pytest tests/unit/checks/test_length_stage.py tests/unit/backends/kicad/test_lowering.py -q`.

## 1. Values and inputs

- [ ] 1.1 Add `dsl/timing.py` (`Delay`, `Loss`, `fs`, `ps`, `ns`, `mdb`, `db`) and export them from `fenolite.dsl` (scenario "Exact conversion"). Proof: `uv run pytest tests/unit/dsl/test_timing.py -q`.
- [ ] 1.2 Add `design.propagation`, `design.loss`, `RuleSet.propagation` and `RuleSet.losses`, and regenerate the schemas (scenario "Inputs round trip"). Proof: `uv run pytest tests/unit/model/test_rules.py -k propagation -q`; `uv run python tools/gen_schemas.py --check`.

## 2. Topologies in the DSL and the model

- [ ] 2.1 Add `PinHandle.__rshift__`, `Chain`, `design.topology`, `design.bridge`, the tree checks and `RuleSet.topologies` (scenarios "A daisy chain through a terminator", "A cycle refused"). Proof: `uv run pytest tests/unit/dsl/test_topology.py -k "daisy or cycle" -q`.
- [ ] 2.2 Read `bridges` from device records (c0248) and report `topology.bridge-missing` at build (scenario "A missing bridge"). Proof: `uv run pytest tests/unit/dsl/test_topology.py -k bridge_missing -q`.
- [ ] 2.3 Add `dsl/protocol.py` (`Usb2`, `Clock`, `design.constrain`) with no defaults (scenario "Kind checked"). Proof: `uv run pytest tests/unit/dsl/test_protocol.py -q`.

## 3. The stage `topology.rules`

- [ ] 3.1 Add `checks/padpath.py` (pad-to-pad shortest copper path, zones refused) with authored benches. Proof: `uv run pytest tests/unit/checks/test_padpath.py -q`.
- [ ] 3.2 Add `checks/topology.py`: delay and loss with strict-side rounding, skew, stubs, order, subjects; insert the stage after `length.rules` (scenarios "Hand-computed delay", "Loads out of order", "Default order"). Proof: `uv run pytest tests/unit/checks/test_topology_stage.py tests/unit/cli/test_check_cmd.py -k "delay or order or default_stages" -q`.
- [ ] 3.3 Summary, evidence and the codes with their `explain.toml` tables (scenarios "Not judged without inputs", "Judgement literals are keys", "An unrouted end"). Proof: `uv run pytest tests/unit/checks -k "codes or input_missing or unrouted" -q`; `uv run pytest tests/consistency -q`.

## 4. Specificity and explained rules

- [ ] 4.1 Add `checks/specificity.py` and its table in `docs/dsl.md` (scenarios "Ranks", "Same bytes"). Proof: `uv run pytest tests/unit/checks/test_specificity.py -k ranks -q`; `uv run pytest tests/unit/backends/kicad/test_lowering.py -k specificity_neutral -q`.
- [ ] 4.2 `rules.shadowed` and `design.rules.precedence("specificity")` (scenarios "A class rule over a net rule", "The net rule governs"). Proof: `uv run pytest tests/unit/checks/test_specificity.py -q`.
- [ ] 4.3 `fenolite check --explain-rules` and `result.rules` (scenario "Governing rule printed"). Proof: `uv run pytest tests/unit/cli/test_check_cmd.py -k explain_rules -q`.

## 5. Lowering

- [ ] 5.1 Lower one-net delays and skews as `length`/`skew` rules, and report `rules.topology-not-lowered` otherwise; record the rows in `docs/formats/kicad/rules.md` with their labels (scenario "One-net delay lowered"). Proof: `uv run pytest tests/unit/backends/kicad/test_lowering.py -k topology -q`.
- [ ] 5.2 Prove one lowered topology `length` rule with `kicad-cli` on 9.0.9 and 10.0.6 (KiCad job in CI, not on the maintainer's PC). Proof: `uv run pytest tests/kicad/rules/test_topology_lowering.py -q` in the KiCad CI jobs.

## 6. Example, docs and guide

- [ ] 6.1 `examples/topologies/`: an authored clock daisy chain with a terminator and a USB pair with a protocol object, catalog parts only. Proof: `uv run pytest tests/unit/checks/test_topology_stage.py -k example -q`; `make residue`.
- [ ] 6.2 Docs: `docs/topologies.md` (new: units, inputs, trees, bridges, constraints, rounding, protocol objects, lowering, specificity), linked from `docs/dsl.md` and `docs/impedance.md`. Proof: `uv run pytest tests/consistency -q`.
- [ ] 6.3 Agent guide: tested lines for `fs`, `ps`, `ns`, `mdb`, `db`, `design.topology` and `--explain-rules` on the pages `rules` and `board-routing`, values marked as examples; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 7. Closing

- [ ] 7.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 7.2 Evidence: register `H-G-TOPO-DELAY` (and `H-K-PRO-TIME-DOMAIN` as `UNKNOWN`, owed) in `docs/hypotheses.md` and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 7.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.
