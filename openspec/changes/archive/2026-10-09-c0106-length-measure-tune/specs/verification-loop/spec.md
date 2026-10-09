## ADDED Requirements

### Requirement: Length rules stage
`fenolite check` SHALL gain the stage `length.rules`, right after `copper.clearance` in `STAGE_ORDER` and so before `drc.kicad`, as "Check stages and statuses" allows. It MUST be a default stage, MUST NOT be in `ORACLE_STAGES`, and MUST be run by `checks.length.length_stage(design, *, project, rules_source, facts_source, evidence) -> StageResult` on the board model that `run_checks` read (`Validation.read.design`), with `Validation.read.evidence` as `evidence`, the validator as `rules_source` when it satisfies `DesignRulesSource` and as `facts_source` when it satisfies `LengthSource`, and `None` for each otherwise.
- **Rules.** With a rules source, the stage MUST judge `rules_source.design_rules(design, project).design`; without one, the design as read, with one `length.input-missing` warning naming the missing rules source. The rules of the kinds `length`, `skew` and `diff_pair_skew` of c0104 are judged. A rule governs a net when its `selector_a` matches the net's `RuleSubject(item_kind="track", net=<name>, netclass=<class>, diff_pair=<base>)`, the base being that of `model.pairs.net_bases` over the design's net names. The governing length rule of a net MUST be the last matching `length` rule in `rule_precedence` order; its governing skew rule the last matching rule of the kinds `skew` and `diff_pair_skew` together, which KiCad writes as one constraint. A governing rule of severity `ignore` MUST judge nothing.
- **Lengths.** With a facts source, the totals MUST be those of `facts_source.length_facts(<checked design>, project=project, nets=<the governed nets>)`; without one, the routed lengths of `geometry-kernel` "Path lengths", with one `length.input-missing` warning naming the length facts. A governed net with a pad and no copper MUST be judged at length 0 (`H-K-NETLEN-RULES`).
- **Length rules.** A total below the `min` or above the `max` of the net's governing `length` rule MUST give one `length.out-of-range` with the rule's severity, whose message names the net, the total, the limit and the rule, and gives the routed, via and die parts in millimetres. `opt` MUST NOT be judged.
- **Skew rules.** The nets governed by one `skew` rule MUST form one group; those governed by one `diff_pair_skew` rule MUST form one group per base. In a group of two nets or more, the skew of a net MUST be its total less the longest total of the group, ties going to the first net name; a skew whose magnitude exceeds the rule's `max` MUST give one `length.skew-out-of-range` with the rule's severity, whose message names the net, its total, the net of the longest total and that total, the skew and `max`. The net of the longest total is never reported.
- **Skip, status and summary.** The stage MUST be skipped with reason `read-refused` when the board read was refused. Its status is `ok` without an issue of severity `error`, `errors` otherwise. `summary` MUST hold `rules` (`{"length": n, "skew": n}`), `nets` (the count of governed nets judged), `major` and `stackup` (those of the facts, `None` without them).
- **Evidence.** `Evidence.combine` of `checks.length.EVIDENCE`, which is `Evidence(Level.INFERRED, hypotheses=("H-K-NETLEN-RULES",))`, `evidence`, `LengthFacts.evidence` and `DesignRules.evidence` when given; `UNVERIFIED` when the stage gave `length.input-missing`.
- The stage MUST run no subprocess, so it needs no `kicad-cli`, and MUST keep "Check is read-only" and "Check output is deterministic".
- The stage belongs to the pipeline of KiCad input only. It MUST NOT be in `checks.documents.DOCUMENT_STAGES` or `OPT_IN_DOCUMENT_STAGES`: `fenolite check` on Altium input ("Document check pipeline") neither runs nor names it, and `--stages length.rules` on such input is the usage error that pipeline gives for a stage it does not hold.

#### Scenario: Pair skew without kicad-cli
- **GIVEN** a project of `tests/_lengthbench.py` whose board holds `SK_P` (one 20 mm track) and `SK_N` (one 21 mm track) and whose rules file holds a `diff_pair_skew` rule (c0104) on `diff_pair SK_` with `max` 0.1 mm; no `kicad-cli` on `PATH`, no `FENOLITE_KICAD_CLI`, and `MACOS_KICAD_CLI` patched to a missing path
- **WHEN** `uv run pytest tests/unit/checks/test_length_stage.py -k pair` runs `fenolite check <project> --stages length.rules --json`
- **THEN** the exit code is 5, no subprocess ran, and the issues hold exactly one `length.skew-out-of-range` error, naming `SK_P` with a skew of −1 mm against `SK_N` at 21 mm

#### Scenario: Minimum on a short net and on a net of pads only
- **GIVEN** a project whose rules file holds a `length` rule with `min` 5 mm and `max` 50 mm on `SHORT` (2.4 mm of track) and on `NOTRK` (two pads, no copper), and a rule with only `opt` 5 mm on `OPTONLY` (2.4 mm of track)
- **WHEN** the stage runs
- **THEN** it gives one `length.out-of-range` error for `SHORT` with total 2.4 mm and one for `NOTRK` with total 0, and nothing for `OPTONLY`

#### Scenario: No length rule
- **GIVEN** `tests/_projects.py::authored_project(tmp_path, major=10, built=True)`
- **WHEN** `fenolite check <project> --stages length.rules --json` runs
- **THEN** the stage has status `ok`, no issue, and `summary.rules` equal to `{"length": 0, "skew": 0}`

#### Scenario: Default stage order
- **GIVEN** the native `two_layer` project and a fake `kicad-cli` 10.0.6 that writes a DRC report and an IPC-D-356 export
- **WHEN** `uv run pytest tests/unit/cli/test_check_cmd.py -k default_stages` runs `fenolite check <project> --json`
- **THEN** `result.stages` names `length.rules` right after `copper.clearance`, and before `drc.kicad`

#### Scenario: Altium input has no length stage
- **GIVEN** the Altium project of the blink sample
- **WHEN** `uv run pytest tests/unit/checks/test_length_stage.py -k document` runs `fenolite check <project> --json`
- **THEN** `result.stages` holds the stages of `DOCUMENT_STAGES` and no `length.rules`, and `checks.documents.ALL_DOCUMENT_STAGES` does not name it

### Requirement: Length stage issue codes
`fenolite.checks.codes.ISSUE_CODES` SHALL also hold these keys with these severities ("Check issue codes"), and `docs/cli-contract.md` MUST document each. Each MUST have a table in `src/fenolite/cli/data/explain.toml`, as every code that `fenolite explain` knows.

| code | severity | when |
|---|---|---|
| `length.out-of-range` | error, warning | a net's total lies outside the `min` and `max` of its governing length rule; the rule sets the severity |
| `length.skew-out-of-range` | error, warning | a net's skew from the longest net of its group exceeds the `max` of its governing skew rule; the rule sets the severity |
| `length.input-missing` | warning | no rules source, or no length facts, so via heights and die lengths are not counted |

#### Scenario: Length literals are keys
- **WHEN** `uv run pytest tests/unit/checks -k codes` collects every issue-code literal under `src/fenolite/checks/`
- **THEN** each `length.*` literal is a key of `ISSUE_CODES` with the severities of this table

#### Scenario: Length codes documented
- **WHEN** `uv run pytest tests/consistency` runs
- **THEN** the three `length.*` codes appear in `docs/cli-contract.md`
