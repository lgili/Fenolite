## Why

A script can declare a differential pair (`DiffPair`, `USB2`); c0073 warns when KiCad would not pair its names. Nothing else reaches KiCad: every class gets the template's pair width, gap and via gap, and no rule kind checks a pair. The review of 2026-10-05 found this as one of the gaps to a complex board (milestone v0.4, `docs/roadmap.md`, "v0.4: proposals on other branches"); the plan had these kinds at v0.6. On `origin/dev` at `9aba2dff` the gap is still whole: `model.rules.RuleKind` holds the twelve kinds of c0071, `SelectorOp` has no pair leaf, and `NetClass` holds four values.

Probes on 9.0.9 and 10.0.6 (2026-10-05, same results) show:

- No pair object: two nets pair by name, and `A.inDiffPair('<base>')` selects them. Digits and underscores may follow the P or N (`D_P0`/`D_N0`), which c0073's rule misses.
- Only custom rules check a pair: `diff_pair_gap` (min, max), `diff_pair_uncoupled` (max), `skew` (max; within each pair with `(within_diff_pairs)`) and `length` (min, max). `opt` is never checked.
- Class pair values are router defaults, not limits. A class pair gap below the class clearance lowers the clearance inside a pair, unless a custom clearance rule governs it.

## What Changes

- **The pair** stays an `Interface` of kind `diff_pair` or `usb2`. A new `model/pairs.py` holds the measured name rule and the base.
- **Class pair values:** `NetClass.diff_pair_width`, `diff_pair_gap`, `diff_pair_via_gap`, in the project file and in `design.rules.netclass(…)`.
- **Five rule kinds:** `diff_pair_gap`, `diff_pair_uncoupled`, `skew`, `diff_pair_skew` (within each pair) and `length`, on both majors.
- **A pair selector:** the leaf `diff_pair <base>`, written `S.inDiffPair('<base>')`, `*` for every pair; `select.pair(usb)` in the DSL. On both sides of a `clearance` rule, it sets a pair's inner clearance.
- **`design.rules.pair(pair, …)`:** a pair's gap, clearance, uncoupled, skew and length rules in one call.
- **The copper check** applies the class pair gap inside a pair as KiCad does, and the explanation of a clearance (c0097) shows the pair gap as a candidate row.
- **The KiCad build:** `build.diff-pair-name` follows the measured rule; `build.interface-not-lowered` only for a pair no rule selects; a new warning, `build.diff-pair-gap-shadowed`, for a pair KiCad would report at its class gap.
- **The Altium build** writes none of it and names all of it. The rule table of c0084 holds one row per neutral kind, so the five kinds get rows with the reason `no-counterpart` (their Altium records are in no public source recorded here); a rule with a pair leaf gives `scope-unsupported`; the class pair values give one `altium.not-lowered` info at `pair-values`. Without these rows an Altium build of a design with a `length` rule would raise `KeyError`.

Size: 6.75 design-days; cut order in the design.

## Prerequisites

What must be on `dev` before this change starts:

- Release `0.3.0` is cut, with c0084 (Altium rule lowering) archived: this change MODIFIES its "Rule lowering table".
- c0097 (copper rule explanation) is on `dev`: the pair gap adds a candidate row to its explanation.
- Of the v0.4 proposals: c0103 lands before this change and this change regenerates "Closed selector grammar" from the text c0103 leaves; c0107 lands before it and this change regenerates "Rule kinds and limits" from the text c0107 leaves.
- c0071 and c0073 are archived on `dev` (2026-10-05): satisfied.

c0105, c0106 and c0110 need this change.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Differential pairs in the model".
- `rules-model`: MODIFIED "Rule kinds and limits", "Closed selector grammar", "Net classes lower to the project file".
- `kicad-file-backend`: ADDED "Net class pair values in project files".
- `design-dsl`: MODIFIED "Net classes in the DSL", "Interfaces in the DSL", "Interface checks in a build"; ADDED "Pair selectors in the DSL", "Pair rules in the DSL".
- `copper-check`: ADDED "Clearance between the nets of a differential pair".
- `kicad-oracle`: ADDED "Differential pair rules are enforced by kicad-cli", "Net class pair values are probed", "Differential pair clearance parity".
- `altium-pcb-writer`: MODIFIED "Rule lowering table" (a requirement of c0084, which is archived first).
- `altium-build`: ADDED "Differential pairs in an Altium build".

## Non-goals

- Shipped values: nowhere, because Fenolite ships none (plan D6).
- Length and skew measured by Fenolite, and meanders: c0106.
- Pair routing: c0110. Impedance targets and tuning profiles: c0105. Time units (`ps`) in rules: nowhere, because the yardstick matches length.
- Renaming nets KiCad does not pair: nowhere, because KiCad's names would differ from the model's.
- `isCoupledDiffPair()`, `fromTo()`, `via_count`: nowhere, because the measured forms cover the yardstick.
- Pair records, pair rules and class pair values written into Altium documents, and pair rules read from them: nowhere for now. No public source recorded in `docs/formats/altium/` states the pair record or the records of the pair and length rule kinds; a later change records those facts first and then turns the rows `exact`. Until then the Altium build names each item (above).

Limits: KiCad never checks `opt`; only `diff_pair_gap` takes a layer clause; the five kinds take one side and the leaves `diff_pair`, `net`, `netclass`; a pair selector needs names KiCad pairs, with letter case; lengths count vias as KiCad does; pair values get no floor warning; the gap warning covers declared pairs only.

## Evidence level required

- New rows `H-K-DRU-PAIR`, `H-K-DRU-PAIRSEL`, `H-K-DIFFPAIR-NAMES-2`, `H-K-PRO-PAIR`, `H-K-COPPER-PAIR`, settled on 9.0.9 and 10.0.6 before merge.
- Model, DSL, lowering and reading: unit scenarios. The Altium rows and messages: unit scenarios; no Altium fact is claimed and no level moves on that side.

## Impact

- New: `model/pairs.py`, `tests/kicad/rules/test_pair_rules.py`, `tests/kicad/project/test_pair_classes.py`.
- Changed: `model/{rules,circuit}.py`, `backends/kicad/{rulemap,lowering,pro}.py`, `backends/altium/rulemap.py`, `checks/clearance.py`, `dsl/{design,select,convert}.py`, `lens/{build,altium}.py`, `cli/data/explain.toml`, schemas, docs (`docs/formats/altium/pcb-copper.md` included: the table "The lowering table" gains five rows).
- Model documents: `circuit.json` and `rules.json` gain keys and values; 0.2.x and 0.3.0 cannot read a document that carries them.
- No source id is added; the block S-0640 to S-0659 that the coordinator reserved for this group is used by c0105 only.
