## 0. Entry check

- [x] 0.1 Read `openspec list` and record the date, base commit and archival state of c0256 (subjects, `findings()`), c0248 (device records), c0252 (interface kinds) and c0246 (ranges); confirm usable dependency surfaces or record scoped deferrals. Confirm `length.rules` directly precedes `placement.rules`, default `rule_precedence` and "Lowered rules follow priority" are unchanged, whether `H-K-PRO-TIME-DOMAIN` has a completed probe, and the decisions of `design.md`. Proof: `npx -y @fission-ai/openspec validate c0258-signal-topologies --strict`; `uv run pytest tests/unit/checks/test_length_stage.py tests/unit/backends/kicad/test_lowering.py -q`.

  Entry inspection 2026-11-01, base `8d74a798`: c0256, c0252 and c0246 have usable implementations but
  remain active changes, not archived. c0248 device records exist; their bridge field is added here.
  `length.rules` directly precedes `placement.rules`; default rule precedence remains priority/name/id.
  `H-K-PRO-TIME-DOMAIN` has only a pending row and no completed proof. Decisions are recorded in
  `design.md`; the available active dependency surfaces are used under the working agreement; no archival claim is made.

## 1. Values and inputs

- [x] 1.1 Add `dsl/timing.py` (`Delay`, `Loss`, `fs`, `ps`, `ns`, `mdb`, `db`) and export them from `fenolite.dsl` (scenario "Exact conversion"). Proof: `uv run pytest tests/unit/dsl/test_timing.py -q`.
- [x] 1.2 Add `design.propagation`, `design.loss`, `RuleSet.propagation` and `RuleSet.losses`, and regenerate the schemas (scenario "Inputs round trip"). Proof: `uv run pytest tests/unit/model/test_rules.py -k propagation -q`; `uv run python tools/gen_schemas.py --check`.

## 2. Topologies in the DSL and the model

- [x] 2.1 Add `PinHandle.__rshift__`, `Chain`, `design.topology`, `design.bridge`, the tree checks and `RuleSet.topologies` (scenarios "A daisy chain through a terminator", "A cycle refused"). Proof: `uv run pytest tests/unit/dsl/test_topology.py -k "daisy or cycle" -q`.
- [x] 2.2 Read `bridges` from device records (c0248) and report `topology.bridge-missing` at build (scenario "A missing bridge"). Proof: `uv run pytest tests/unit/dsl/test_topology.py -k bridge_missing -q`.
- [x] 2.3 Add `dsl/protocol.py` (`Usb2`, `Clock`, `design.constrain`) with no defaults (scenario "Kind checked"). Proof: `uv run pytest tests/unit/dsl/test_protocol.py -q`.

## 3. The stage `topology.rules`

- [x] 3.1 Add `checks/padpath.py` (pad-to-pad shortest copper path, zones refused) with authored benches. Proof: `uv run pytest tests/unit/checks/test_padpath.py -q`.
- [x] 3.2 Add `checks/topology.py`: delay and loss with strict-side rounding, skew, stubs, order, subjects; insert the stage after `length.rules` (scenarios "Hand-computed delay", "Loads out of order", "Default order"). Proof: `uv run pytest tests/unit/checks/test_topology_stage.py tests/unit/cli/test_check_cmd.py -k "delay or order or default_stages" -q`.
- [x] 3.3 Summary, evidence and the codes with their `explain.toml` tables (scenarios "Not judged without inputs", "Judgement literals are keys", "An unrouted end"). Proof: `uv run pytest tests/unit/checks -k "codes or input_missing or unrouted" -q`; `uv run pytest tests/consistency -q`.

## 4. Specificity and explained rules

- [x] 4.1 Add `checks/specificity.py` and its table in `docs/dsl.md` (scenarios "Ranks", "Same bytes"). Proof: `uv run pytest tests/unit/checks/test_specificity.py -k ranks -q`; `uv run pytest tests/unit/backends/kicad/test_lowering.py -k specificity_neutral -q`.
- [x] 4.2 `rules.shadowed` and `design.rules.precedence("specificity")` (scenarios "A class rule over a net rule", "The net rule governs"). Proof: `uv run pytest tests/unit/checks/test_specificity.py -q`.
- [x] 4.3 `fenolite check --explain-rules` and `result.rules` (scenario "Governing rule printed"). Proof: `uv run pytest tests/unit/cli/test_check_cmd.py -k explain_rules -q`.

## 5. Lowering

- [x] 5.1 Lower proven whole-net delays and differential protocol skews as `length`/`skew` rules, and report `rules.topology-not-lowered` otherwise; record the rows in `docs/formats/kicad/rules.md` with their labels (scenario "One-net delay lowered"). Proof: `uv run pytest tests/unit/backends/kicad/test_lowering.py -k topology -q`.
- [ ] 5.2 Prove one lowered topology `length` rule with `kicad-cli` on 9.0.9 and 10.0.6 (KiCad job in CI, not on the maintainer's PC). Proof: `uv run pytest tests/kicad/rules/test_topology_lowering.py -q` in the KiCad CI jobs.
  - 2026-11-04, local KiCad 10.0.6 (macOS `kicad-cli`): the over-budget case (`max_fs=100000`, 20 mm on F.Cu = 118000 fs) failed. KiCad reported `length_out_of_range` of `fenolite_0_topology_clk_delay` (max 16.9492 mm, actual 20.0000 mm) on the net's two pads, and the test looked only at the track's uuid. The test now matches any track or pad of CLK, as `_lengthbench.net_uuids` does for the length kind, and requires the lowered rule's name in the violation. Both cases pass with the canary fired (2 passed, 3.19 s). The 9.0.9 run and the two CI jobs are still owed, so the task stays open.

## 6. Example, docs and guide

- [x] 6.1 `examples/topologies/`: an authored clock daisy chain with a terminator and a USB pair with a protocol object, catalog parts only. Proof: `uv run pytest tests/unit/checks/test_topology_stage.py -k example -q`; `make residue`.
- [x] 6.2 Docs: `docs/topologies.md` (new: units, inputs, trees, bridges, constraints, rounding, protocol objects, lowering, specificity), linked from `docs/dsl.md` and `docs/impedance.md`. Proof: `uv run pytest tests/consistency -q`.
- [x] 6.3 Agent guide: tested lines for `fs`, `ps`, `ns`, `mdb`, `db`, `design.topology` and `--explain-rules` on the focused `signal-topologies` page (the existing `rules` page is at 250 lines/11997 bytes), linked from `rules` and with command lines in `board-routing`, values marked as examples; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 7. Closing

- [ ] 7.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Proof: `make check-fast`, and the required jobs green on the exact commit.
- [x] 7.2 Evidence: register `H-G-TOPO-DELAY` (and `H-K-PRO-TIME-DOMAIN` as `UNKNOWN`, owed) in `docs/hypotheses.md` and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [x] 7.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.

## Validation record — 2026-11-01

- [x] 7.4 Declare the conservative native topology mapping's inferred evidence and include the
  library-only LibrePCB package in the live backend inventory. Proof:
  `uv run pytest tests/unit/backends/test_evidence_declared.py tests/unit/test_evidence_matrix_page.py -q`;
  `uv run python tools/gen_evidence_matrix.py --check`.
  Passed 2026-11-01: 37 evidence-declaration, generated-matrix and capability tests.
  LibrePCB declares only its existing inferred seed subset; its generic board matrix stays empty.

- Focused dependency, DSL, model, device, graph, stage, specificity, lowering and CLI regressions:
  380 passed. Additional strict-lowering and subject-name collision checks passed after final review.
- Consistency: 662 passed, 41 expected mutating-command skips. Agent guide: 119 passed, 19 KiCad-10-only
  skips on the available KiCad 9 environment. Hypothesis register: 38 passed. Changelog selection:
  8 passed, one optional MCP SDK skip. Codes/input/unrouted selection: 33 passed.
- Ruff, formatting, pyright, generated schemas/guide/evidence checks, public residue scan and strict
  OpenSpec validation pass. The core dependency list remains empty.
- **5.2 remains open:** its two-case canary oracle is authored and collects, but neither required
  KiCad 9.0.9/10.0.6 CI execution is claimed. Existing kind evidence is separate from conversion proof.
- **7.1 remains open:** workers were instructed to run focused checks only. The integration owner
  schedules `make check-fast`, publication and the required CI jobs on the exact pushed commit.
  No push, full local suite or CI result is claimed here.
- Block-cluster integration, 2026-11-01: 862 focused topology, stage, lowering, catalog, block-runner,
  saved-copper, lock, guide and import/evidence regressions passed (19 installed-KiCad-major skips).
  Legacy rules/pad query-order assertions remain intact. Lint, format, pyright src, all four generated
  outputs, residue and strict OpenSpec pass; the root-scheduled full gate and exact-head CI remain open.
