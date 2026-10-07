## Context

- **Scope.** The review of 2026-10-05 named the gaps to a complex board; since 2026-10-07 the group is milestone v0.4 (`docs/roadmap.md`, "Milestone names" and "v0.4: proposals on other branches", where the row of c0104 holds its id and slug only). The gap this change closes, in the review's words: "a differential pair lowered to KiCad: pair net names, class pair width, gap and via gap, rule kinds for gap, uncoupled length, skew and length". The plan's rules row put `length`, `skew` and `diff_pair_gap` at v0.6, and c0071 and c0073 list them as non-goals; this change pulls them forward with the uncoupled length, which the yardstick's pairs need.
- **What exists** on `origin/dev` at `9aba2dff` (2026-10-07). c0071 and c0073 are archived (2026-10-05), so the living specs hold their text, and the MODIFIED requirements of this change are copies of that living text with this change's edits only (compared word by word on that commit).
  - `model.circuit.Interface(name, kind, members)`. The DSL's `DiffPair(p, n)` gives kind `diff_pair` with the roles `p` and `n`, and `USB2(dp, dn, …)` gives kind `usb2` with `dp` and `dn` (c0073). No other pair type exists in `src/`.
  - `NetClass` holds `clearance`, `track_width`, `via_diameter`, `via_drill` and `description`. `lowering.NETCLASS_KEYS` writes the four lengths, and `lower_netclass` copies every other key of the project's `Default` entry, so every written class carries the template's `diff_pair_width` 0.2, `diff_pair_gap` 0.25 and `diff_pair_via_gap` 0.25 mm. `pro.ProjectClass` reads four values.
  - `model.rules`: twelve kinds (c0071); the ops `all`, `net`, `netclass`, `ref`, `layer`, `item_kind`, `and`, `or` and `not`; `Rule.min/opt/max` in nm. `rulemap.rule_nodes` writes only `min`, `opt` and `max` inside a constraint, and `lift_rule` keeps a rule with any other constraint child opaque. The token inventory loads `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `length` and `constraint/within_diff_pairs` since 9 (`H-K-TOK-RULES-FLOOR`; the flag is written as a list, and a bare atom disables the rules).
  - `lens.build`: `PAIR_KINDS`, `is_pair` (names equal except for a last character `P`/`N` or `+`/`-`, `H-K-DIFFPAIR-NAMES`) and `interface_checks`, which gives one `build.interface-not-lowered` info per `diff_pair` and `usb2` interface and `build.diff-pair-name`.
  - `checks.clearance.ClearanceResolver`: subjects of item kind, net, class, reference and layer; every leaf compared without letter case; `k` is the larger class clearance (c0029, c0068).
  - A DRC violation of any type becomes a `kicad.drc.<type>` finding, with one `explain` entry for the family, so new types need no registry.
  - The Altium build (c0084, implemented on `dev`, two tasks open, not archived). `backends.altium.rulemap.TABLE` holds one row per kind of `model.rules.RuleKind`: eight `exact` rows and four `no-counterpart` rows; `lower()` looks a rule's row up by its kind (`_ROWS[rule.kind]`), and the scenario "Every kind has a row" of c0084's "Rule lowering table" compares the kinds of the model with the table. A kind without a row raises `KeyError` in the build and fails that scenario. `rulemap._leaf` refuses every leaf other than `net` and `netclass` with `scope-unsupported`. Each rule that is not written gives one `altium.not-lowered` warning at `design-rules/<kind>`. `lens.altium` names the rule values of the net classes in one info at `rules` when no PCB document is written (with a document the class clearance, width and via values become rule records), and names `diff_pair`, `i2c`, `spi`, `uart` and `usb2` interfaces in one info at `interfaces`. `read.scope.parse_scope` has a closed grammar with no pair function. The word "pair" in `rulemap.ScopeForm` means a rule with two scopes, not a differential pair.
  - c0097 (branch `codex/c0097-copper-rule-explain`, not on `dev`): `ClearanceResolver.explain` returns the candidate rows `rule:<name>`, `class:<name>`, `floor` and the zone row, taken from the resolver's own candidates; its design says that a later pair-gap source adds a candidate row.
- **Measured on 2026-10-05.** Scratch benches were written with the `write_board` of the branch `review-roadmap-complex-board`: 0.2 mm tracks on `F.Cu`, rows 4 mm apart, the canary scoped to `CANARY_A`. DRC ran as `kicad-cli pcb drc --format json --severity-all -o <report> <board>` on the local 10.0.6, and as the same command in the pinned 9.0.9 image (`docker run --rm --platform linux/amd64 -v <bench folder>:/p -w /p -e HOME=/tmp kicad/kicad:9.0.9@sha256:e638b79b… kicad-cli pcb drc …`). The canary fired in every run, and the two majors gave the same outcomes on every row except the one marked.

  1. *Rule kinds*, project `{}`, pairs 0.3 mm apart edge to edge unless said; several rules files ran on one board, so a row recurs:

     | rule (condition `A.inDiffPair('<row>')` unless said) | row | reported |
     |---|---|---|
     | `diff_pair_gap (min 0.35mm)` | GA | `diff_pair_gap_out_of_range` "minimum gap 0.3500 mm; actual 0.3000 mm", naming both tracks |
     | the same | GB, 0.4 mm apart | nothing |
     | `diff_pair_gap (max 0.25mm)` | GC | `diff_pair_gap_out_of_range` "maximum gap 0.2500 mm" |
     | `diff_pair_gap (min 0.35mm) (max 0.5mm)` | GA; GB | reported; nothing |
     | `diff_pair_gap (opt 0.5mm)` | GD | nothing |
     | `diff_pair_gap (min 0.25mm) (opt 0.3mm) (max 0.35mm)`; `(min 0.35mm) (opt 0.35mm) (max 0.35mm)` | GE; GF | nothing; reported "minimum gap 0.3500 mm" |
     | `(layer "F.Cu")` with `diff_pair_gap (min 0.35mm)`; the same with `(layer "B.Cu")` | GA; GC, both on `F.Cu` | reported; nothing |
     | min 0.35 on the two net names | GE | reported |
     | min 0.35 on the positive net's name only | GF | reported |
     | min 0.35 on `GG_A` and `GG_B`, which do not pair by name | GG | nothing |
     | `diff_pair_uncoupled (max 2mm)` | UA: the positive track 3 mm longer | `diff_pair_uncoupled_length_too_long` "actual 3.0000 mm" |
     | the same | UB: 1 mm longer | nothing |
     | the same | UC: equal tracks 3 mm apart | nothing: parallel segments count as coupled at any distance |
     | `skew (max 0.5mm) (within_diff_pairs)` | SA: 20 and 21 mm | `skew_out_of_range` on the shorter track, "actual -1.0000 mm; target net length 21.0000 mm (from SA_N)" |
     | the same | SB: 20 and 20.2 mm | nothing |
     | `skew (max 0.5mm)` on four net names | SC 20/20 mm, SD 23/23 mm | `skew_out_of_range` on both SC tracks, -3 mm against SD_N |
     | `skew (max 0.5mm) (within_diff_pairs)` on four net names | SE 20/20, SF 23/23 | nothing |
     | the same | SG 20/21, SH 23/23 | on SG_P only |
     | `skew (opt 0.1mm) (within_diff_pairs)` | SM 20/21 | nothing |
     | `length (min 25mm)`; `(max 15mm)`; `(min 15mm) (max 25mm)`; `(opt 30mm)`; `(min 25mm) (max 30mm)`; `(min 15mm) (opt 20mm) (max 25mm)`, on a net name | 20 mm tracks | `length_out_of_range` "min length 25.0000 mm; actual 20.0000 mm"; reported; nothing; nothing; reported; nothing |
     | `length (max 20.5mm)` | 10 mm on `F.Cu`, a 0.6 mm via, 10 mm on `B.Cu` | reported: actual 21.5800 mm on 10.0.6, 21.5450 mm on 9.0.9 (the two majors differ here only) |

  2. *Selectors.* `A.inDiffPair('*')` reported every pair 0.3 mm apart, not GB (0.4 mm), not GG (no pair by name) and not UC. `A.inDiffPair('GD_')`, the base with its underscore, selected GD; `A.inDiffPair('gc')` selected nothing on `GC_P`/`GC_N`, so the base keeps its letter case, unlike `NetName`. `A.NetClass == 'DPG'` selected the pair of class DPG.
  3. *Order.* `diff_pair_gap` on `*` (min 0.35 mm) then on GA (min 0.25 mm): GA not reported; with the two rules swapped, reported. The same for `length` on `A.NetName == 'L*'` (max 15 mm) then on `LA` (max 25 mm).
  4. *Names*, `diff_pair_gap (min 0.35mm)` on both net names: `TA_P1`/`TA_N1`, `TB_P_2`/`TB_N_2` and `TDP1`/`TDN1` are pairs; `TC_P1`/`TC_N2` and `TG_PA`/`TG_NA` are not. `A.inDiffPair('TE_')` selects `TE_P1`/`TE_N1`; `A.inDiffPair('TF_P')` selects nothing on `TF_P1`/`TF_N1`. So KiCad skips a trailing run of digits and underscores before the polarity character, and the base is the text before that character. c0073's rule is the case of an empty run.
  5. *Class values*, a project from `synthesize_project` with the pair keys set by hand, the nets in classes by exact-name patterns, pairs 0.15 mm apart unless said:

     | class: clearance / pair gap / pair width / pair via gap (mm) | row | reported |
     |---|---|---|
     | DPA: 0.2 / 0.1 / 0.3 / 0.5 | CA_P/CA_N | nothing: the pair gap lowers the clearance inside the pair |
     | DPB: 0.2 / 0.25 / 0.2 / 0.25 | CB_P/CB_N | `clearance` "netclass 'DPB' clearance 0.2000 mm; actual 0.1500 mm" |
     | DPA | CC_A/CC_B, which do not pair | `clearance` (netclass 'DPA') |
     | DPC: 0.1 / 0.4 / 0.3 / 0.25 | CF_P/CF_N of 0.2 mm tracks | nothing: the pair gap and width are no limits |
     | DPA | two 0.6 mm vias of a pair, 0.3 mm apart | nothing: the via gap is no limit |

  6. *Custom rules against the class values* (class DPA unless said):

     | set-up | row | reported |
     |---|---|---|
     | a board-wide custom `clearance (min 0.2mm)` | CA, 0.15 mm | `clearance` "rule 'board' clearance 0.2000 mm; actual 0.1500 mm" |
     | the same, then `clearance (min 0.1mm)` on `A.inDiffPair('CA') && B.inDiffPair('CA')` | CA | nothing; CC still reported |
     | the same with `A.inDiffPair('CB') && AB.isCoupledDiffPair()` | CB (DPB) | nothing |
     | no board rule; `diff_pair_gap (min 0.1mm)` on CB | CB | `clearance` (netclass 'DPB'): a gap rule does not lower the clearance |
     | project `min_clearance` 0.12 mm | 0.11 mm; 0.13 mm | `clearance` "board minimum clearance 0.1200 mm" and `diff_pair_gap_out_of_range` "netclass 'DPA' (diff pair) minimum gap 0.1200 mm"; nothing |
     | project `min_clearance` 0.2 mm and the pair clearance rule (min 0.1 mm) | 0.15 mm | `diff_pair_gap_out_of_range` "netclass 'DPA' (diff pair) minimum gap 0.2000 mm", no `clearance` |
     | the same, then `diff_pair_gap (min 0.1mm)` on the pair | 0.15 mm | nothing |

  None of these benches is committed; task group 1 turns every row into a recorded probe. The measurements were made on the branch `review-roadmap-complex-board` and were not repeated on `dev`; the board and rules writers they used did not change in what these rows read (the kinds and the selector are new), and task group 1 repeats every row on `dev` before any table is filled.
- **Constraints.** Stdlib only, integers only, no value shipped (plan D6). A kind and a selector are written for a major only when a probe proved them there.

## Goals / Non-Goals

**Goals:**
- A script declares a pair's class values and its gap, uncoupled length, skew and length limits, and KiCad's DRC checks each on both majors.
- What KiCad takes as a pair, Fenolite takes as a pair, by one measured rule.
- `check` judges the clearance inside a pair as KiCad's DRC does.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Approximating a selector, as in c0071: a selector outside a kind's grammar is refused.

## Decisions

1. **A pair is an interface; no new entity.** The model's pair is an `Interface` whose kind is a key of `model.pairs.PAIR_ROLES`: `diff_pair` (positive `p`, negative `n`) and `usb2` (`dp`, `dn`). `pairs.pair_nets(interface)` gives its two net ids. Its constraints are not fields of it: width, gap and via gap are class values (Decision 3), and the limits are rules that select the pair (Decisions 4 and 5).
   - Rejected: a `DiffPair` entity with typed fields. It would be a third spelling of one fact beside c0073's two kinds; KiCad stores no pair object to write it to; Altium's pair record (`DifferentialPairs6`, a name and two nets) maps onto the interface as it is.
   - Rejected: constraint fields on `Interface`, an entity that power and I2C share.

2. **One name rule, measured** (`H-K-DIFFPAIR-NAMES-2`, measurement 4). `model.pairs.split_pair_name(name)` removes the longest trailing run of digits and `_` (the tail), then takes the last character as the polarity when it is `P`, `N`, `+` or `-`; the base is the text before it. `coupled_name(name)` swaps `P` and `N`, or `+` and `-`, keeping base and tail. Two names pair when the first one's polarity is `P` or `+` and the second is its coupled name; letter case counts. The eight probe cases of `H-K-DIFFPAIR-NAMES` keep their outcomes.
   - `lens.build.is_pair` and `pair_hint` call these functions, so `build.diff-pair-name` stops warning on `D_P0`/`D_N0`, and the hint proposes `coupled_name(first)`.
   - Rejected: keeping c0073's last-character rule. It warns on names KiCad pairs, and its base is wrong for `inDiffPair()` (`TF_P` selects nothing).

3. **Class pair values.** `NetClass` gains `diff_pair_width`, `diff_pair_gap` and `diff_pair_via_gap` (nm or `None`). `NETCLASS_KEYS` maps them to the class keys of the same names, so synthesis and update write them as they write the four lengths, `None` keeps the base value, and `read_project` and `apply_project` read them back.
   - KiCad uses them as its interactive router's defaults; none is a DRC limit (measurement 5). One effect matters: a class pair gap below the class clearance lowers the clearance between the two nets of each pair of the class, where no custom clearance rule governs them (measurements 5 and 6). A board minimum clearance above the pair gap adds a gap check at that minimum (measurement 6).
   - No floor warning for the three values: no board-setup key bounds them, and the board minimum's effect on the pair gap is the copper check's floor (Decision 8).
   - Rejected: values per pair. KiCad holds them per class, and a class per pair would multiply classes for the router to read.

4. **Five rule kinds.**

   | kind | written constraint | limits | layer clause | DRC type |
   |---|---|---|---|---|
   | `diff_pair_gap` | `diff_pair_gap` | `min`, `opt`, `max` | yes | `diff_pair_gap_out_of_range` |
   | `diff_pair_uncoupled` | `diff_pair_uncoupled` | `max` | no | `diff_pair_uncoupled_length_too_long` |
   | `skew` | `skew` | `opt`, `max` | no | `skew_out_of_range` |
   | `diff_pair_skew` | `skew`, with the child `(within_diff_pairs)` after the limits | `opt`, `max` | no | `skew_out_of_range` |
   | `length` | `length` | `min`, `opt`, `max` | no | `length_out_of_range` |

   - KiCad's DRC checks `min` and `max` and never `opt` (measurement 1). `opt` is still written and read back, as the `opt` of `track_width` is: KiCad's interactive tools take it as their target, c0105 writes a pair gap with `min` = `opt` = `max`, and c0106's meanders tune to a target length. `docs/formats/kicad/rules.md` says that `opt` is not checked. Rejected: refusing `opt`, as c0071 did for kinds on which only `min` was measured; here `opt` was measured, and two later changes need it.
   - Two skew kinds: `skew` compares every net the rule selects with the longest one, for a matched group; `diff_pair_skew` compares the two nets of each pair (rows SC to SH). Rejected: one kind and a flag field on `Rule`, a field that one kind reads; `via_drill` set the precedent of a kind with its own written form.
   - The kinds take side A only, and the leaves `diff_pair`, `net` and `netclass` combined with `and`, `or` and `not` (measurements 1 and 2). `diff_pair_gap` takes a layer clause, one rule per layer as for the other kinds (rows GA and GC with `(layer …)`), which c0105 needs for a gap per layer. The other four take none: it was not measured on them, and a length or a skew sums a net over its layers. `ref` and `item_kind` select pads, footprints and item types, which these checks do not read by.
   - `KIND_SUPPORT` holds {9, 10} for each, from the probes `dru-kind-<kind>`, so c0071's "Kind support by major" applies as written.
   - What KiCad measures stays KiCad's: a length counts a via by the stack-up (row of the via: 1.58 mm on 10.0.6, 1.545 mm on 9.0.9), and an uncoupled length counts parallel segments as coupled at any distance (row UC), so a `diff_pair_gap` rule with a `max` is what bounds how far a pair spreads.
   - Rejected: `via_count` (`too_many_vias`), `fromTo()` lengths and time units (`ps`): none is in the yardstick, which matches length; pin-to-pin length is c0106's.

5. **The pair selector.** `SelectorOp` gains the leaf `diff_pair`, whose value is a pair base or `*`. It lowers to `S.inDiffPair('<value>')` and lifts back. It selects the items on the two nets of every pair whose base is the value, or the value followed by `_` (c0073's cases `pn` and `pn-full`), and every pair for `*`; letter case counts (measurement 2). `RuleSubject.diff_pair` is the base of the subject's net when the design holds its coupled net.
   - `SELECTOR_SUPPORT["diff_pair"]` follows the probe `dru-cond-diff_pair`, a clearance bench as for every key. The six kinds of v0.1 and the three hole kinds take it with the rest of the grammar; `clearance` takes it on both sides, which is how the clearance inside a pair is written (measurement 6).
   - The value is the base, not the interface's name. The condition then needs no circuit to be written or read, a hand-written `inDiffPair()` lifts, and the copper check matches it from net names, as KiCad does. The DSL computes the base from the interface (Decision 7).
   - Rejected: `or(net X_P, net X_N)` written by the DSL instead of a leaf. It works for one pair (row GE), but cannot say "every pair" and reads back as two nets. Rejected: `isCoupledDiffPair()`, which does what `inDiffPair` on both sides does (measurement 6) and would be a second spelling.

6. **The clearance inside a pair is a rule the user asks for.** KiCad lowers the clearance inside a pair to the class pair gap only where no custom clearance rule governs the pair. A Fenolite design often has one: `minimum(clearance=…)` writes a board-wide rule. A clearance rule with `diff_pair` leaves on both sides, later in KiCad's order, sets the gap again (measurement 6). Likewise a board minimum clearance above the pair gap makes KiCad check the coupled gap at that minimum unless a `diff_pair_gap` rule governs the pair. Fenolite writes these rules only when the user asks (`pair(clearance=…, gap_min=…)` or `rule()`), and the build names the pairs that need them (Decision 9).
   - Rejected: writing a pair clearance rule from the class value without being asked. "Fenolite lowers only the design's rules" (`rules-model`), and the value a pair needs near its pads is the user's.

7. **The DSL.**
   - `design.rules.netclass(…, diff_pair_width=None, diff_pair_gap=None, diff_pair_via_gap=None)`: lengths, as the four other values.
   - `select.pair(x)`: a `DiffPair`, a `USB2` or another `Interface` of a pair kind gives `diff_pair <base>`, and `DslError` naming both nets and the coupled name when its names do not pair (Decision 2); a string is taken as a base, and `"*"` selects every pair.
   - `design.rules.pair(pair, *, gap_min=None, gap_max=None, clearance=None, uncoupled_max=None, skew_max=None, length_min=None, length_max=None, severity="error", priority=1)` records, as `rule()` does, one rule per given group: `diff_pair_gap` (`gap_min`, `gap_max`), `clearance` (the pair on both sides), `diff_pair_uncoupled`, `diff_pair_skew` and `length`, named `pair:<pair name>:<gap|clearance|uncoupled|skew|length>`. The interface joins the design.
   - Priority 1 puts the pair's rules after every priority-0 rule. Class minimums of `minimum(netclass=…)` also have priority 1 and the names `min_<kind>_<class>`; ties are broken by name, and `pair:` sorts after `min_`, so the pair's rules come later in KiCad's order and govern its items (`rules-model`, "Lowered rules follow priority"; measurement 3).
   - Rejected: class values on `pair()`. They belong to the class of the two nets, which KiCad's router reads.

8. **The copper check follows KiCad inside a pair** (`H-K-COPPER-PAIR`). For two subjects on the two nets of one pair, both in one class whose `diff_pair_gap` is below its `clearance`, the class value `k` is that gap, with source `pair-gap:<class>`. A governing rule replaces it as it replaces a class value, the board minimum stays a floor above it, and a `diff_pair` leaf is compared with its letter case (measurement 6). Without this, `check` reports every coupled pair below its class clearance, which KiCad passes (row CA).
   - Rejected: a documented difference. A pair below its class clearance is the normal coupled pair, so each would be a false error.

9. **The build.**
   - `build.diff-pair-name` uses the rule of Decision 2.
   - `build.interface-not-lowered` is given for a pair interface that no rule of the design selects through a `diff_pair` leaf; the message says that KiCad then knows the pair by its names only.
   - `build.diff-pair-gap-shadowed` (warning): the nets of a `diff_pair` or `usb2` interface pair by name and share a model class whose `diff_pair_gap` `g` is set, and KiCad would report two tracks of the pair `g` apart: the clearance in force between them (Decision 8, with the target's switches) is above `g`, or the board minimum clearance that the build writes is above `g` and no `diff_pair_gap` rule selects the pair. The message names the pair, `g` and what governs; the hint names `pair(clearance=…, gap_min=…)`. Nets that pair by name without an interface are not checked: the script did not call them a pair.
   - Rejected: an error. KiCad loads such a project, and a pair routed wider than its class gap is clean.

10. **Reading.** `read_rules` lifts the five kinds and the leaf. A `skew` constraint whose children are its limits and the list `(within_diff_pairs)` lifts as `diff_pair_skew`, without the list as `skew`; `S.inDiffPair('v')` lifts as `diff_pair v`. A rule of these kinds with a limit outside its row, a time unit, a bare `within_diff_pairs` atom, a layer clause on a kind that takes none, or a condition outside its kind's selectors stays opaque with `rules.kept-opaque`, and is written back verbatim.
    - Rejected: keeping hand-written pair rules opaque, as today. KiCad would apply them, and the model, the copper check and c0106's length stage would not see them.

11. **Altium: a row for every new kind, and nothing written.** c0084's table is closed over `RuleKind`, so this change adds five rows to `rulemap.TABLE` and to the table "The lowering table" of `docs/formats/altium/pcb-copper.md`, each `no-counterpart` with a note in the form of the `creepage` row: the record of the Altium rule that would carry the kind is in no public source recorded here. An Altium build then gives one warning per pair or length rule at `design-rules/<kind>` and lists it in `result.rules.not_lowered`, as c0084 does for `silk_clearance`.
    - A rule of an `exact` kind with a `diff_pair` leaf (the pair clearance rule of Decision 6) is refused by `_leaf` with `scope-unsupported`; no code changes for it, and the requirement and a scenario pin it.
    - The three class values are written nowhere. With a PCB document the `rules` info of the classes is filtered out, because the class clearance, width and via values are then rule records; the pair values would vanish without a word. So one info `altium.not-lowered` at `pair-values` names the classes that hold a pair value, with and without a document.
    - Pair interfaces stay in the `interfaces` info whether or not a rule selects them: the narrower condition of `build.interface-not-lowered` (Decision 9) is KiCad's, where names and rules carry the pair.
    - Reading: `lift` and `parse_scope` do not change, so no Altium document reads as a pair rule or a pair leaf; `fenolite diff` and equivalence compare rules through the model, where the new kinds and the leaf are plain values.
    - Rejected: rows that map to Altium's own pair, matched-length and length rules. "A row MUST be `exact` only when `pcb-copper.md` records the constraint and the keys of its record" (c0084), and no fact row exists; guessing keys would write records nothing has verified.
    - Rejected: a fifth reason such as `not-recorded`. The `creepage` row already uses `no-counterpart` with a note for a rule whose record is not known; one more reason would be a second spelling.
    - Rejected: leaving the Altium side to a later change. The build would raise for a valid design, and c0084's completeness scenario would fail on the day this change merges.

12. **Order with other changes.**
    - c0071 and c0073 are archived on `dev`. The six MODIFIED requirements of `rules-model` and `design-dsl` are the living text of `9aba2dff` with this change's additions; no open change on `dev` holds a delta of any of them.
    - "Rule lowering table" (`altium-pcb-writer`) is an ADDED requirement of c0084, which is open on `dev`. c0084 lands and is archived first; this change's MODIFIED copy is c0084's text of `9aba2dff` with one bullet, one clause of the `lift` bullet, five words in a scenario and one scenario added. If c0084's text moves before it is archived, task 0.1 regenerates the copy.
    - c0097 is on `dev` first (the order of the review of 2026-10-07: c0096, c0097 and c0099 come in before the complex-board proposals). The explanation bullet of "Clearance between the nets of a differential pair" names its capability `copper-rule-explanation`.
    - Inside v0.4, by the order the review of 2026-10-07 fixed: c0103 (the `area` leaf) modifies "Closed selector grammar" and lands first; this change lands second and regenerates its copy from the text c0103 leaves, adding the `diff_pair` row, the grammar clause of the five kinds and the two scenarios. c0107 turns its new kind into a MODIFIED "Rule kinds and limits" and its row into "Rule lowering table"; c0107 lands before this change, which regenerates both copies from the text c0107 leaves ("seventeen" becomes the count that is true then). c0103's design says the same about "Closed selector grammar".
    - c0105 depends on this change and regenerates any delta of its own to "Net classes lower to the project file". Task 0.1 checks all of them.
    - Schemas: `circuit.json` and `rules.json` are regenerated by this change and, among the v0.4 proposals, by c0105, c0107, c0113 and c0114 (`rules.json`); each is additive, and whichever lands later runs `tools/gen_schemas.py` on the merged model.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/pairs.py` (new) | `PAIR_ROLES`, `PairName(base, polarity, tail)`, `split_pair_name`, `coupled_name`, `pair_base(positive, negative)`, `pair_nets(interface)`, `net_bases(names)` (net name → base, for nets whose coupled net is among `names`) |
| `src/fenolite/model/circuit.py` | `NetClass.diff_pair_width`, `diff_pair_gap`, `diff_pair_via_gap` |
| `src/fenolite/model/rules.py` | five `RuleKind` values; `diff_pair` in `SelectorOp` and `LEAF_OPS`; `RuleSubject.diff_pair`; its match in `Selector.matches` |
| `schemas/fenolite.model.v0/circuit.json`, `rules.json` | regenerated |
| `src/fenolite/backends/kicad/rulemap.py` | rows of `KIND_MAP`, `LIMITS`, `KIND_SELECTORS`, `KIND_SUPPORT`; `KIND_FLAGS = {"diff_pair_skew": "within_diff_pairs"}`; `diff_pair` in `SELECTOR_KEYS`; the `inDiffPair` writer and reader |
| `src/fenolite/backends/kicad/lowering.py` | three rows of `NETCLASS_KEYS`; `H-K-DRU-PAIR` in `EVIDENCE` |
| `src/fenolite/backends/kicad/pro.py` | three fields of `ProjectClass`; read, apply and update of them |
| `src/fenolite/backends/altium/rulemap.py` | five rows of `TABLE`, reason `no-counterpart`, with notes |
| `src/fenolite/lens/altium.py` | the info at `pair-values` for classes that hold a pair value |
| `src/fenolite/checks/clearance.py` | the subject's `diff_pair`; the pair gap as class value, source `pair-gap:<class>`; the leaf's letter case; the `pair-gap` candidate row of `explain` (c0097) |
| `src/fenolite/dsl/select.py` | `pair(x)` |
| `src/fenolite/dsl/design.py`, `dsl/convert.py` | `Rules.netclass` keywords and `NetClassSpec` fields; `Rules.pair`; `PAIR_RULE_NAMES` |
| `src/fenolite/lens/build.py` | `is_pair` and `pair_hint` on `model.pairs`; the info's condition; `build.diff-pair-gap-shadowed` in `BUILD_ISSUE_CODES` |
| `src/fenolite/cli/data/explain.toml` | the new code; the new meaning of `build.interface-not-lowered` |
| unit tests | `tests/unit/model/test_pairs.py` (new), `tests/unit/backends/kicad/test_rulemap_pairs.py` (new), `test_lowering_netclass.py`, `test_pro_read.py`, `test_pro_update.py`, `tests/unit/checks/test_clearance.py`, `tests/unit/dsl/test_select.py`, `tests/unit/dsl/test_pair_rules.py` (new), `tests/unit/lens/test_interface_checks.py`, `tests/unit/backends/altium/test_rulemap.py`, `tests/unit/lens/test_altium_rules.py`, `tests/unit/checks/test_copper_rule_review.py` (c0097's file) |
| oracle tests | `tests/kicad/rules/_pairbench.py` and `test_pair_rules.py` (new), `_paircases.py` (more cases), `tests/kicad/project/test_pair_classes.py` (new), `tests/kicad/copper/_copperparity.py` (pair cases), `tests/kicad/rules/test_rule_design.py` (the pair design), `tests/kicad/_probes.py`, `docs/evidence/kicad/probes/*.json` |
| docs | `docs/formats/kicad/rules.md`, `project.md`, `copper.md`, `docs/formats/altium/pcb-copper.md` (five rows of "The lowering table"), `docs/altium.md` if it lists what a build keeps in the model, `docs/dsl.md`, `docs/design-model.md`, `docs/hypotheses.md`, `docs/cli-contract.md` |

No CLI command or option changes. No file is added under `tests/data/`: the benches are generated by the tests, and the probe outcomes go to `docs/evidence/kicad/probes/`. No source is added: S-0010 and S-0038 document the constraint types and `inDiffPair()`, and S-0020 and S-0029 are the two oracles (all four are rows of `docs/evidence/sources.md` on `9aba2dff`).

New names of this change, for the cross-check among the v0.4 proposals: hypothesis ids `H-K-DRU-PAIR`, `H-K-DRU-PAIRSEL`, `H-K-DIFFPAIR-NAMES-2`, `H-K-PRO-PAIR`, `H-K-COPPER-PAIR` (none in `docs/hypotheses.md` on `9aba2dff`); issue code `build.diff-pair-gap-shadowed`; the `where` value `pair-values` of `altium.not-lowered`; the resolver source `pair-gap:<class>`; model fields `NetClass.diff_pair_width`, `diff_pair_gap`, `diff_pair_via_gap` and `RuleSubject.diff_pair`; rule kinds `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew`, `length`; selector op `diff_pair`; DSL names `select.pair` and `design.rules.pair`; rule names `pair:<pair>:<group>`; probe ids `dru-pair-*`, `dru-pair-sel-*`, `dru-cond-diff_pair`, `pro-pair-*`, `copper-resolve-pair-*`.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-DRU-PAIR | `diff_pair_gap` (`min`, `max`, with a layer clause or none), `diff_pair_uncoupled` (`max`), `skew` (`max`, with and without `(within_diff_pairs)`) and `length` (`min`, `max`), written as `rulemap` states, give `diff_pair_gap_out_of_range`, `diff_pair_uncoupled_length_too_long`, `skew_out_of_range` and `length_out_of_range` on the probed rows and none on the controls; `opt` is accepted and not checked; the gap and uncoupled checks need nets that pair by name; the later of two rules governs (S-0010, S-0038, S-0020, S-0029) | `tests/kicad/rules/test_pair_rules.py` | probes `dru-kind-<kind>` for the five kinds and `dru-pair-<case>` give the outcomes of measurements 1 and 3, with the scoped canary firing, on 9.0.9 and 10.0.6; `KIND_SUPPORT` equals the `present` outcomes |
| H-K-DRU-PAIRSEL | `S.inDiffPair('<v>')` selects the items of the two nets of every pair whose base is `v` or `v` followed by `_`, every pair for `*`, comparing letter case; on both sides of a `clearance` rule it sets the clearance between the two nets of a pair (S-0038, S-0020, S-0029) | `tests/kicad/rules/test_pair_rules.py -k select`; `tests/kicad/rules/test_rule_conditions.py -k diff_pair` | `dru-cond-diff_pair` `present`, and the `dru-pair-sel-<case>` probes as measurement 2, on both majors |
| H-K-DIFFPAIR-NAMES-2 | Two nets pair when their names are equal except for a polarity character, `P` then `N` or `+` then `-`, that is followed in both by the same run of digits and underscores, possibly empty; the base is the text before it (S-0020, S-0029) | `tests/kicad/rules/test_diffpair_names.py` | the new `dru-diffpair-<case>` probes as measurement 4, and the eight cases of c0073 unchanged, on both majors |
| H-K-PRO-PAIR | A class `diff_pair_gap` below the class clearance lowers the clearance between the two nets of a pair of that class where no custom clearance rule governs them; a governing custom rule replaces it; a board minimum clearance above the gap is a floor and adds a gap check at that minimum unless a `diff_pair_gap` rule governs; `diff_pair_width`, `diff_pair_via_gap` and the class gap are no DRC limits (S-0010, S-0038, S-0020, S-0029) | `tests/kicad/project/test_pair_classes.py` | the `pro-pair-<case>` probes as measurements 5 and 6, on both majors |
| H-K-COPPER-PAIR | KiCad's clearance in force inside a pair follows the copper check's pair rule (Decision 8) on rows below, at and above the value (S-0010, S-0038) | `tests/kicad/copper/test_copper_parity.py -k pair` | every `copper-resolve-pair-<case>` probe `equal` on both majors |

All five start `INFERRED`, with the measurements of Context as their first record. `H-K-DIFFPAIR-NAMES` keeps its level for its cases; its result gains "partly refuted: a tail of digits and underscores may follow the polarity; extended by H-K-DIFFPAIR-NAMES-2".

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| the five kinds, both majors | KICAD-VERIFIED (9.0.x, 10.0.x) | `dru-kind-*`, `dru-pair-*` |
| the pair selector | KICAD-VERIFIED (9.0.x, 10.0.x) | `dru-cond-diff_pair`, `dru-pair-sel-*` |
| the name rule | KICAD-VERIFIED (9.0.x, 10.0.x) | `dru-diffpair-*` |
| class pair values in the project | KICAD-VERIFIED (9.0.x, 10.0.x) | `pro-pair-*` |
| the copper check inside a pair | KICAD-VERIFIED (9.0.x, 10.0.x) | `copper-resolve-pair-*` |
| a built pair design loads its rules | KICAD-VERIFIED (9.0.x, 10.0.x) | `test_rule_design.py` with the scoped canary |
| model, DSL, lowering, reading, build checks | mechanical | unit tests |
| the five Altium rows, the `pair-values` info, the `scope-unsupported` refusal | mechanical; no Altium fact is claimed | `tests/unit/backends/altium/test_rulemap.py`, `tests/unit/lens/test_altium_rules.py` |
| the `pair-gap` candidate row | mechanical (it shows the resolver's value) | `tests/unit/checks/test_copper_rule_review.py -k pair_gap` |

`dru.EVIDENCE` keeps its level; `lowering.EVIDENCE` names `H-K-DRU-PAIR` beside its hypotheses.

## Risks / Trade-offs

- [The name order decides between a pair rule and a class minimum of the same priority] → documented in `docs/dsl.md`; a user rule of priority 1 named after `pair:` governs instead, as the tie rule says, and `build.diff-pair-gap-shadowed` still names a pair whose gap it undoes.
- [The `diff_pair` leaf keeps letter case while the other leaves do not] → the DSL takes the base from the net names, so a script cannot get it wrong; a hand-written lower-case base selects nothing in KiCad and in the check alike.
- [`build.diff-pair-name` changes its verdict] → it stops warning on names KiCad pairs; every pair of the old rule is a pair of the new one, so no name starts to warn.
- [Distant parallel tracks count as coupled] → documented in `rules.md`; `pair(gap_max=…)` bounds the spread.
- [An `opt` that nothing checks] → `rules.md` and `docs/dsl.md` say so, as for `track_width`; `pair()` takes no `opt`, so a target is written only through `rule()` or by c0105 and c0106.
- [A later 10.0.x changes the implicit pair rules] → the `pro-pair-*` and `copper-resolve-pair-*` probes fail before the check drifts.
- [A time unit in a hand-written rule] → kept opaque and written back verbatim; time units go nowhere in v0.4, as c0105 and c0106 also say, because the yardstick matches length.
- [An Altium user reads `no-counterpart` as "Altium has no such rule"] → each row's note and the warning's message say that the record is not known from a public source, as the `creepage` row does.

## Migration Plan

- Additive. A design without pairs, pair values or pair rules builds the same bytes. `circuit.json` and `rules.json` written before this change load, the three class fields as `None`. The other direction does not work: **0.2.x and 0.3.0 cannot read a `circuit.json` that carries one of the three keys, or a `rules.json` that holds one of the five kinds or a `diff_pair` leaf**, because the reader of the canonical form is strict, as after every earlier additive change of the model. `SCHEMA_VERSION` stays `"0"`. The changelog line and `docs/design-model.md` say so (tasks 8.4 and 2.2), and a build regenerates `.fenolite/`.
- Altium: a design without pair content builds the same bytes. A design that already declared a pair builds the same Altium files and gains no message; the new messages appear only with the new values and kinds.
- A hand-written `.kicad_dru` with pair rules now lifts them; the written text keeps names and clause order.
- `check` stops reporting a coupled pair below its class clearance where KiCad passes it. `build.diff-pair-name` stops warning on `X_P0`/`X_N0`, and `build.interface-not-lowered` disappears for pairs that rules select. `CHANGELOG.md` says all three.
- Rollback: remove the kinds from `KIND_SUPPORT` and the key from `SELECTOR_SUPPORT`; pair rules are then refused or kept opaque, and classes take the template's pair values again.

## Budget (6.75 days)

| part | days |
|---|---|
| entry check, register rows | 0.25 |
| probes recorded: pair kinds, selector, order and names, on both majors | 1.0 |
| probes recorded: class values and custom rules, on both majors | 0.25 |
| model: `pairs.py`, class fields, kinds, leaf, subject, schemas | 0.75 |
| rules: tables, flag, `inDiffPair` writer and reader, self-check | 1.0 |
| project: three class keys written, updated and read | 0.5 |
| copper check: pair gap, leaf case, parity rows on both majors | 1.0 |
| DSL: `netclass` keywords, `select.pair`, `rules.pair` | 0.75 |
| build: name rule, info, `build.diff-pair-gap-shadowed`, explain entries, built pair design | 0.5 |
| Altium: five table rows and the page's rows, the `pair-values` info, two scenarios; the `pair-gap` candidate row | 0.25 |
| documentation and closing | 0.5 |

Cut order: (1) `design.rules.pair()` (0.5 day), since `rule()` with `select.pair()` writes the same rules; (2) `build.diff-pair-gap-shadowed` (0.25 day); (3) the `skew` kind for groups of nets, keeping `diff_pair_skew` (0.1 day); (4) the narrower condition of `build.interface-not-lowered` (0.1 day). Never cut: the class pair values, the kinds `diff_pair_gap`, `diff_pair_uncoupled`, `diff_pair_skew` and `length`, the selector and its probe, the name rule, and the copper check's pair gap, without which `check` reports pairs that KiCad passes.

## Open Questions

- **Should `pair()` write the clearance rule by default, at the class pair gap, when that gap is below the clearance in force?** Default: no; the user gives `clearance=`, and `build.diff-pair-gap-shadowed` names the pairs that need it.
- **Should `pair()` take targets (`gap_opt`, `length_opt`)?** Default: no; `rule()` writes a target, and the class pair gap is the router's.
- **Should a build warn about a `diff_pair` leaf that selects no pair of the design?** Default: no, as for a `net` leaf that names no net today.
- **Should the three class values get floor warnings like the four lengths?** Default: no; the board minimum's effect on the pair gap is modelled (Decision 8), and none on the width was measured.
