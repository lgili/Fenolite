## Context

- **Scope.** Plan, v0.2b deliverables: "full rules → `.kicad_dru` (courtyard/silk/hole-to-hole/annular/creepage)"; plan's rules row: "`rules`: … + `courtyard_clearance`, `silk_clearance`, `hole_to_hole`, `annular_width`, `creepage` (v0.2b)". Plan v0.2b acceptance: "a fixture of two overlapping rules resolved by `kicad-cli` as the emission order predicts (D6)". Plan D6: Fenolite ships no requirement tables; values come from the user.
- **What exists.**
  - `model.rules.RuleKind` = `clearance`, `track_width`, `via_diameter`, `via_drill`, `hole_size`, `edge_clearance`; `Selector` ops `all`, `net`, `netclass`, `ref`, `layer`, `item_kind`, `and`, `or`, `not`; `Rule(name, kind, selector_a, selector_b, layers, min, opt, max, severity, priority)`.
  - `rulemap`: the condition writer and `lift_rule`, `SELECTOR_SUPPORT` (every key on both majors), `RULE_ISSUE_CODES`; `lowering.lower_rules`, `lower_minimums`, `MINIMUM_KEYS`, `FLOOR_OVER_RULES` (empty: `H-K-PRO-MIN-RULE` refuted, `H-K-PRO-MIN-RULE-2`), `RULES_OVER_CLASSES` = {9, 10}; `dru.read_rules` keeps any other kind opaque with `rules.kept-opaque`.
  - The living text of "Conflicts with board-setup minimums are reported" still says that, until the probes have run, every `FLOOR_OVER_RULES` entry holds {9, 10}. The probes ran in c0054; the code holds the measured, empty table.
  - `design.rules.netclass()` and `design.rules.minimum()` (c0054). No constructor takes a selector.
  - The token inventory loads `annular_width`, `hole_clearance`, `hole_to_hole`, `courtyard_clearance`, `silk_clearance` and `creepage` since 9 (`rules-type-*`, `H-K-TOK-RULES-FLOOR`). The project template keeps `min_hole_clearance` 0.25 mm, `min_hole_to_hole` 0.25 mm, `min_via_annular_width` 0.1 mm and `min_silk_clearance` 0 verbatim.
  - c0047 measured creepage on 10.0.x: a `creepage` rule on two nets (`A.NetName == 'A' && B.NetName == 'B'`) brackets Fenolite's value on its slot bench (`H-K-AN-CREEP-2`).
  - c0026 left `annular_width`, `hole_to_hole` and `hole_clearance` open as kinds; c0031 rejected zone connection and thermal relief as kinds.
- **Measured on 2026-10-05** (scratch benches built with `tests/kicad/rules/_rulebench.py`, `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally; recorded by task 1.2):
  - The bench canary must be scoped to its own net (`A.NetName == 'CANARY_A'`). An unscoped canary rule matches every pair, and KiCad reports one violation per item pair, so it hides the constraint under test.
  - `hole_to_hole` (1 mm) on two vias whose holes are 0.7 mm apart gives a `hole_to_hole` violation on both majors; 9.0.9 writes the limit as `0.9995 mm` in the description.
  - `hole_clearance` gives `hole_clearance` for a via hole near a track of another net, with the condition on either item's net. An NPTH hole near a track gave no violation; not explained, not used.
  - `annular_width` gives `annular_width` on both majors.
  - `courtyard_clearance` gives `courtyards_overlap` ("rule 'c' clearance 1.0000 mm; actual 0.5100 mm") with no condition, with `A.Type == 'Footprint'` and with `A.Reference == 'CY1'`, never with `A.memberOfFootprint('CY1')`, on both majors.
  - `silk_clearance` gives `silk_overlap` and `silk_over_copper`, also between a footprint's silkscreen and its own fields, courtyard, fabrication lines and pads: its control footprint was flagged too.
  - `creepage` on 9.0.9: on c0047's slot bench, no `creepage` violation below or above Fenolite's value, while the canary fired.
- **Constraints.** Stdlib only, integers only, no shipped values. Every kind and selector is written for a major only when a probe proved it there.

## Goals / Non-Goals

**Goals:**
- Every rule kind the plan names can be declared in the script, written to `.kicad_dru`, and read back from a hand-written file.
- Nothing is written that KiCad would ignore on the target major.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Approximating a selector. A selector outside a kind's grammar is refused, as today.

## Decisions

1. **The six kinds.**

   | kind | written constraint | limits | DRC types |
   |---|---|---|---|
   | `hole_to_hole` | `hole_to_hole` | `min` | `hole_to_hole` |
   | `hole_clearance` | `hole_clearance` | `min` | `hole_clearance` |
   | `annular_width` | `annular_width` | `min` | `annular_width` |
   | `courtyard_clearance` | `courtyard_clearance` | `min` | `courtyards_overlap` |
   | `silk_clearance` | `silk_clearance` | `min` | `silk_overlap`, `silk_over_copper` |
   | `creepage` | `creepage` | `min` | `creepage` |

   - Only `min` was measured, so only `min` is accepted; `opt` or `max` gives `rules.unsupported-limit`. A `min` of 0 is allowed for these kinds (no overlap).
   - Rejected: `physical_clearance`, `disallow`, thermal and zone kinds (not in the plan's list, or rejected by c0031).

2. **Selectors per kind.** `rulemap.KIND_SELECTORS` names, per kind, what its sides take:
   - `clearance`: as today, both sides.
   - `hole_to_hole`, `hole_clearance`, `annular_width`: side A in the closed grammar, no side B, no layer clause.
   - `courtyard_clearance`: `all`, or `ref` values combined with `and`, `or` and `not`, with no glob; `ref v` is written `A.Reference == 'v'` (`H-K-DRU-COURTYARD`). No side B, no layer clause.
   - `silk_clearance`: `all` only. Its matches include a footprint's own items, so a selector narrower than the board promises a precision it does not have.
   - `creepage`: `net` and `netclass` leaves combined with `and`, `or` and `not`, on side A and side B, as c0047's bench writes it. No layer clause.
   - The other five old kinds keep their rules. A selector outside its kind's entry gives `rules.unsupported-selector`, never dropped.

3. **Kind support by major.** `rulemap.KIND_SUPPORT` maps each kind to the majors whose `dru-kind-<kind>` probe recorded `present`; the six old kinds hold {9, 10} (`H-K-DRU-KIND`). A rule of a kind whose entry lacks the target gives `rules.kind-unchecked` (error). It is a target refusal: `RulesLossError.droppable` is true when it is the only kind of error, and `--allow-lossy` drops the rule with `rules.dropped-for-target`. From the scratch probes, creepage holds {10} and the other five new kinds {9, 10}.
   - Rejected: writing creepage for 9 with a warning. The file would hold a rule that the target's DRC does not report, and `check` would pass a board that the user believes is checked.

4. **Reading.** `read_rules` lifts a rule of a new kind when its constraint, limits and condition are inside that kind's entries; a courtyard condition `A.Reference == 'v'` lifts to `ref v`. A courtyard rule written with `memberOfFootprint` stays opaque with `rules.kept-opaque` naming the reason, because writing it back as `A.Reference` would change what KiCad checks.

5. **The DSL constructor.** `design.rules.rule(name, kind, *, where=ALL, between=None, layers=(), min=None, opt=None, max=None, severity="error", priority=0)` records one rule; `fenolite.dsl.select` gives `net(…)`, `netclass(…)`, `ref(…)`, `item(…)` and `ALL`, combined with `&`, `|` and `~`.
   - The DSL refuses at the call what does not depend on the target: an unknown kind, no limit, a bad length, `min` above `opt` or `max`, a negative `min`, `between` for a kind other than `clearance` and `creepage`, a duplicate name, an unknown severity. What depends on the target (glob, kind support, selector support) is refused by the lowering, with its codes.
   - A `Net`, `Part` or class name can be passed where a name is expected, so a rename in the script follows the object.
   - `to_model` adds the rules after those of `minimum()`, in call order, with the id `derived_id("rul", "dsl", "rule:named:<name>")`. Priorities keep the meaning of `rules-model`: 0 is written first and governs least; among the others, 1 governs most.
   - Rejected: one keyword method per kind (`hole_to_hole(...)`, …): twelve methods for one shape, and selectors would still be needed.

6. **The overlapping-rule fixture.** The plan's acceptance is already proved for clearance (`H-K-DRU-ORDER`, both majors). The bench is repeated with two `hole_to_hole` rules (0.5 mm then 1 mm, and swapped), so the order rule is shown for a new kind.

7. **Floors of the new kinds.** The template keeps board-setup minimums for holes, rings and silk. Probe `pro-min-rule-<kind>-tM` checks, per major, that a board-wide rule below the template minimum governs: a gap between the rule and the minimum gives no violation (`H-K-PRO-MIN-RULE-3`). If it governs, nothing more is written. If not, `MINIMUM_KEYS` gains the key of that kind for that major (`min_hole_clearance`, `min_hole_to_hole`, `min_via_annular_width`, `min_silk_clearance`), and `lower_minimums` writes it from the governing board-wide rule, as for the five old keys.

8. **The stale paragraph.** "Conflicts with board-setup minimums are reported" says that the tables hold the claims until the probes run. It is replaced by the measured state: `FLOOR_OVER_RULES` is empty on both majors, and the unit scenarios that need another value set it themselves.

9. **Cut order.** First the DSL constructor's operators (`&`, `|`, `~`; keep `select.and_`, `or_`, `not_`), then the floor probe's fallback (keep the probe), then `silk_clearance`. Never cut: the kinds named in the plan for which a probe passes, the reading and the support table.

## Files and public API

- `src/fenolite/model/rules.py`: `RuleKind` gains the six kinds.
- `src/fenolite/backends/kicad/rulemap.py`: `KIND_SUPPORT`, `KIND_SELECTORS`, the constraint table, the `Reference` writer and lift for courtyards, `rules.kind-unchecked` in `RULE_ISSUE_CODES`.
- `src/fenolite/backends/kicad/lowering.py`: kind support in `lower_rules`; `MINIMUM_KEYS` only if Decision 7's fallback applies.
- `src/fenolite/dsl/select.py` (new): `Select`, `ALL`, `net`, `netclass`, `ref`, `item`; `src/fenolite/dsl/design.py`: `Rules.rule`, `RuleSpec`.
- `schemas/fenolite.model.v0/rules.json` regenerated.
- Tests: `tests/unit/backends/kicad/test_rulemap.py`, `test_lowering.py`, `test_dru.py` (extended); `tests/unit/dsl/test_rule_constructor.py`; `tests/kicad/rules/test_rule_kinds_new.py`, `test_rule_order.py` (extended), `test_rule_floors.py`.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-DRU-KIND-2 | Each of `hole_to_hole`, `hole_clearance`, `annular_width`, `courtyard_clearance`, `silk_clearance` and `creepage`, written as Decision 1 and 2 state, gives a violation of its DRC types on the probed item and none on the control item; `creepage` is reported on 10.0.6 and not on 9.0.9 (S-0020, S-0029) | `tests/kicad/rules/test_rule_kinds_new.py` | probes `dru-kind-<kind>` per major; `KIND_SUPPORT` equals their `present` outcomes; the canary fires in every run |
| H-K-DRU-COURTYARD | `courtyard_clearance` selects a footprint by `A.Reference == '<ref>'` and not by `A.memberOfFootprint('<ref>')` (S-0020, S-0029) | `tests/kicad/rules/test_rule_kinds_new.py -k courtyard` | probes `dru-courtyard-reference` `present` and `dru-courtyard-member` `absent` on both majors |
| H-K-PRO-MIN-RULE-3 | A board-wide rule of `hole_clearance`, `hole_to_hole`, `annular_width` or `silk_clearance` whose `min` is below the template's board-setup minimum governs: a gap between the two gives no violation (S-0020, S-0029) | `tests/kicad/rules/test_rule_floors.py` | probes `pro-min-rule-<kind>-tM`; `present` on both majors keeps `MINIMUM_KEYS` unchanged, any `absent` applies Decision 7's fallback for that kind and major |

Ids used without changing their level: `H-K-DRU-KIND`, `H-K-DRU-COND`, `H-K-DRU-GLOB`, `H-K-DRU-ORDER`, `H-K-TOK-RULES-FLOOR`, `H-K-PRO-MIN-RULE-2`, `H-K-AN-CREEP-2`.

## Risks / Trade-offs

- [Creepage refused for KiCad 9 surprises a user] → the error names the kind, the target and `--allow-lossy`; `fenolite analyze` (c0047) still measures creepage on either major.
- [`silk_clearance` reports a footprint's own silkscreen] → documented in `docs/formats/kicad/rules.md`; board-wide only.
- [A probe flips on a later 10.0.x or 9.0.x] → `KIND_SUPPORT` is pinned to the probe files, and the probe test fails before the table drifts.
- [NPTH holes in `hole_clearance`] → unexplained on the bench; the requirement promises only what the via bench shows, and the fact row says so.

## Migration Plan

- Additive: new kinds and a new DSL method. A design without them builds the same bytes.
- A hand-written `.kicad_dru` with rules of the new kinds now lifts them instead of keeping them opaque. The written text keeps the rule names and clause order (`kicad-file-backend`), so a rebuild over such a file writes the same rules.
- Rollback: remove the kinds from `KIND_SUPPORT`; rules of those kinds are refused or kept opaque again.

## Open Questions

- **Should `creepage` for KiCad 9 be written with a warning instead of refused?** Default: refused (Decision 3).
- **Should `hole_to_hole`, `hole_clearance` and `annular_width` take a layer clause?** Default: no, until a probe shows what a layer means for a hole.
- **Should `opt` and `max` be accepted for `annular_width`?** Default: no, until measured.
