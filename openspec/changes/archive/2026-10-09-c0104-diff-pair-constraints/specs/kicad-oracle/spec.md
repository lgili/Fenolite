## ADDED Requirements

### Requirement: Differential pair rules are enforced by kicad-cli
`tests/kicad/rules/test_pair_rules.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-DRU-PAIR` and `H-K-DRU-PAIRSEL` on the running `kicad-cli`, on benches of `tests/kicad/rules/_rulebench.py` with pairs of 0.2 mm tracks on `F.Cu` 0.3 mm apart edge to edge, a `{}` project, rules written by `rulemap`, and the canary scoped to its own net, because the pairs are closer than the canary's 3 mm ("Rules proofs carry a canary"). DRC MUST be judged only from the JSON report.
- **Kinds.** Probe `dru-kind-<kind>` MUST record `present` when the probed row has its DRC type and the control row none: `diff_pair_gap` with `min 0.35mm` on a pair 0.3 mm apart (control 0.4 mm), and with `max 0.25mm`; `diff_pair_uncoupled` with `max 2mm` on a pair whose positive track is 3 mm longer (control 1 mm); `diff_pair_skew` with `max 0.5mm` on pairs of 20 and 21 mm (control 20 and 20.2 mm); `skew` with `max 0.5mm` on two pairs of 20 and 23 mm, whose shorter nets are reported; `length` with `min 25mm`, with `max 15mm`, and with both limits, on 20 mm tracks (control `min 15mm` with `max 25mm`).
- **Cases.** Probes `dru-pair-<case>` MUST record: `opt` alone on `diff_pair_gap`, `skew` and `length` (`absent`); `opt` beside `min` and `max` on `diff_pair_gap` and `length`, on a row inside the two limits (`absent`) and on a row below `min` (`present`); a layer clause on `diff_pair_gap` naming the pair's layer (`present`) and another layer (`absent`); a gap rule on two nets that do not pair by name (`absent`); a gap rule on the positive net's name only (`present`); equal tracks 3 mm apart under an uncoupled maximum of 2 mm (`absent`); `diff_pair_skew` on two pairs of 20/20 and 23/23 mm (`absent`); two `diff_pair_gap` rules and two `length` rules that match one row, the later one passing it (`present` when the row is not reported, and reported with the two swapped).
- **Selector.** `dru-cond-diff_pair`, recorded by the op benches of `tests/kicad/rules/test_rule_conditions.py` (`rules-model`, "Closed selector grammar"), MUST record `present` when a clearance rule on `A.inDiffPair('<base>')` gives the probe pair's violation and not the control pair's. Probes `dru-pair-sel-<case>` MUST record the base with its `_` (`present`), the base without it (`present`), `*` (`present`), the base in lower case (`absent`), and a clearance rule with `inDiffPair` on both sides after a board-wide clearance rule (`present` when the pair is not reported).
- **Names.** `tests/kicad/rules/test_diffpair_names.py` MUST also record, under `dru-diffpair-<case>`, the cases of `H-K-DIFFPAIR-NAMES-2`: `X_P1`/`X_N1`, `X_P_2`/`X_N_2` and `XP1`/`XN1` (`present`), `X_P1`/`X_N2` and `X_PA`/`X_NA` (`absent`), and the base before the polarity against the name without its last character for `X_P1`/`X_N1` (`present` and `absent`), each case with its own `X`.
- The outcomes MUST be recorded in both probe files. `rulemap.KIND_SUPPORT` for the five kinds and `SELECTOR_SUPPORT["diff_pair"]` MUST equal the `present` outcomes, and the facts MUST be written to `docs/formats/kicad/rules.md` with sources S-0020 and S-0029 and their labels.

#### Scenario: Pair kinds on both majors
- **WHEN** `uv run pytest tests/kicad/rules/test_pair_rules.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** the five `dru-kind-*` probes of the pair kinds and `dru-cond-diff_pair` record `present`, the cases of `opt` alone record `absent`, the layer clause selects only its layer, and the canary fires in every run

#### Scenario: Names with a tail on both majors
- **WHEN** `uv run pytest tests/kicad/rules/test_diffpair_names.py -rA` runs on both majors
- **THEN** the new cases record the outcomes above, and the eight cases of `H-K-DIFFPAIR-NAMES` keep theirs

#### Scenario: Built pair rules load
- **GIVEN** the rules design of `tests/_rulesdesign.py` with a `USB2` pair and a `d.rules.pair(…)` call that gives every group
- **WHEN** `uv run pytest tests/kicad/rules/test_rule_design.py -rA` builds it for the running major
- **THEN** the written `.kicad_dru` holds the five pair rules and loads, as the scoped canary proves

### Requirement: Net class pair values are probed
`tests/kicad/project/test_pair_classes.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-PRO-PAIR` on the running `kicad-cli`, with benches written through the triad path with net classes, exact-name patterns and the canary scoped to `CANARY_A`, as "Net-class rules are enforced by kicad-cli" writes its benches, and pairs of 0.2 mm tracks on `F.Cu`. DRC MUST be judged only from the JSON report, and every custom rule MUST come after the canary rule unless a row says otherwise.
- **Class rows**, each recorded under `pro-pair-<case>`: a pair 0.15 mm apart in a class of clearance 0.2 mm and `diff_pair_gap` 0.1 mm (`gap-lowers`, `absent` when no `clearance` violation names it); the same with `diff_pair_gap` 0.25 mm (`gap-above`, `present`); two nets that do not pair, in the first class (`not-a-pair`, `present`); a pair 0.15 mm apart in a class of clearance 0.1 mm, `diff_pair_gap` 0.4 mm and `diff_pair_width` 0.3 mm (`no-limits`, `absent` when no violation names it); two 0.6 mm vias of a pair 0.3 mm apart under a `diff_pair_via_gap` of 0.5 mm (`via-gap`, `absent`).
- **Custom rule rows**: a board-wide clearance rule of 0.2 mm written before the canary (`rule-shadows`, `present` when the first pair is reported); then a clearance rule of 0.1 mm with `inDiffPair` on both sides (`rule-restores`, `absent`); a `diff_pair_gap` rule of 0.1 mm on the second pair without a board rule (`gap-rule-clearance`, `present`: its clearance violation stays); a project `min_clearance` of 0.12 mm with pairs 0.11 and 0.13 mm apart in the first class (`floor`, `present` when only the first is reported, with `clearance` and `diff_pair_gap_out_of_range`); a project `min_clearance` of 0.2 mm, a pair 0.15 mm apart and the pair clearance rule, without and with a `diff_pair_gap` rule of 0.1 mm (`floor-gap`, `present`, and `floor-gap-rule`, `absent`).
- The outcomes MUST be recorded in both probe files, and the facts written to `docs/formats/kicad/project.md` with sources S-0020 and S-0029 and their labels.

#### Scenario: Class values on both majors
- **WHEN** `uv run pytest tests/kicad/project/test_pair_classes.py -rA` runs on the local KiCad 10.0.6 and inside the pinned 9.0.9 image
- **THEN** every `pro-pair-*` probe records the outcome stated above, and the canary fires in every run

### Requirement: Differential pair clearance parity
`tests/kicad/copper/test_copper_parity.py` SHALL compare, under `-k pair`, the verdicts of `check_copper` with those of `kicad-cli pcb drc` on pair rows, as "Copper verdict parity canaries" compares its rows, on 9.0.9 and 10.0.6 (`H-K-COPPER-PAIR`).
- **Rows.** Two nets that pair by name, both in a class of clearance 0.3 mm and `diff_pair_gap` 0.15 mm, as tracks at `g − 10 µm`, `g` and `g + 10 µm` of the value `g` in force, in four cases: the class alone (`g` 0.15 mm, source `pair-gap`); a board-wide clearance rule of 0.3 mm (`g` 0.3 mm, source the rule); that rule followed by a clearance rule of 0.15 mm with the pair on both sides (`g` 0.15 mm); and a board minimum of 0.2 mm without a rule (`g` 0.2 mm, source `floor`). A control row of two nets of the class that do not pair, 0.2 mm apart, MUST be reported by both.
- **Probes.** Each case MUST be recorded as `copper-resolve-pair-<case>`: `equal` when every row agrees, and `different` otherwise. KiCad's verdict is the `clearance` violation alone; a `diff_pair_gap_out_of_range` violation is not compared.

#### Scenario: Pair parity on both majors
- **WHEN** `uv run pytest tests/kicad/copper/test_copper_parity.py -k pair -rA` runs on 9.0.9 and on 10.0.6
- **THEN** the four `copper-resolve-pair-*` probes record `equal`, and every bench's canary violation is present
