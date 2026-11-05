## ADDED Requirements

### Requirement: Topology stage
`fenolite check` SHALL gain the default stage `topology.rules`, right after `length.rules` in `STAGE_ORDER`, as "Check stages and statuses" allows. It MUST run no tool, MUST NOT be in `ORACLE_STAGES` or `DOCUMENT_STAGES`, MUST be skipped with `no-topology` when the design holds none and with `read-refused` when the board read was refused, and every issue MUST carry subjects (c0256).

#### Scenario: Default order
- **GIVEN** the native `two_layer` project and a fake `kicad-cli` 10.0.6
- **WHEN** `uv run pytest tests/unit/cli/test_check_cmd.py -k default_stages` runs `fenolite check <project> --json`
- **THEN** `result.stages` names `topology.rules` right after `length.rules`, skipped with `no-topology`

### Requirement: Topology stage summary and evidence
The stage's `summary` SHALL hold `topologies`, `constraints` (count per kind), `judged` and `not_judged`; its evidence MUST be `Evidence.combine` of `Evidence(Level.INFERRED, hypotheses=("H-G-TOPO-DELAY",))` and the read's evidence, and `UNVERIFIED` when it gave `topology.input-missing`.

#### Scenario: Not judged without inputs
- **GIVEN** the example of `examples/topologies/` with the propagation of `In1.Cu` removed
- **WHEN** `uv run pytest tests/unit/checks/test_topology_stage.py -k input_missing` runs the stage
- **THEN** it gives `topology.input-missing`, `not_judged` counts the constraints on that layer, and the stage evidence is `UNVERIFIED`

### Requirement: Topology judgement codes
`fenolite.checks.codes.ISSUE_CODES` SHALL hold `topology.delay-out-of-range`, `topology.skew-out-of-range`, `topology.loss-over-budget`, `topology.stub-too-long` and `topology.order`, each of severity `error` or `warning` as its constraint sets, with a table in `explain.toml` and a line in `docs/cli-contract.md`.

#### Scenario: Judgement literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each of these five `topology.*` literals is a key of `ISSUE_CODES` with the severities `error` and `warning`

### Requirement: Topology input codes
`fenolite.checks.codes.ISSUE_CODES` SHALL hold `topology.bridge-missing` (error), `topology.input-missing` (warning), `topology.path-through-zone` (warning) and `topology.unrouted` (info), with a table in `explain.toml` and a line in `docs/cli-contract.md`; a constraint given `input-missing`, `path-through-zone` or `unrouted` MUST NOT be judged.

#### Scenario: An unrouted end
- **GIVEN** the example of `examples/topologies/` with no copper to `U4`
- **WHEN** `uv run pytest tests/unit/checks/test_topology_stage.py -k unrouted` runs the stage
- **THEN** it gives one `topology.unrouted` info naming `U4-CLK`, and no delay issue for the path to `U4`

### Requirement: Governing rules explained by check
`fenolite check --explain-rules` SHALL add `result.rules`: for each subject (a net, or a pad, track or via kind of a net) and rule kind matched by at least two rules, `{subject, kind, governing, rank, overrides}`, with rules as `{name, id, priority, rank}`, sorted by subject then kind, computed with `rule_precedence` and running no tool.

#### Scenario: Governing rule printed
- **GIVEN** the rules of `rules-model`, "A class rule over a net rule"
- **WHEN** `uv run pytest tests/unit/cli/test_check_cmd.py -k explain_rules` runs `fenolite check <project> --stages model.validate --explain-rules --json` with no `kicad-cli`
- **THEN** `result.rules` holds one entry for `CLK` and `track_width` whose `governing` is the class rule and whose `overrides` holds the net rule, and no subprocess ran
