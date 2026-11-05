# Design: c0403

The private report stays in the private project folder. Each section names the code path, the decision and
the authored fixture. No value, name or shape of the private board is used in a fixture.

## F5: zero-size pad in the shadowed-rule pass

`checks.specificity.subjects` asks `checks.padpath.model_pads` for every pad. Before c0364 a circular pad of
size 0 built a one-point `PadCopper` of width 0, which `PadCopper.__post_init__` refuses, and `check` ended
with `FEN-1001`. c0364 (`75f9e995`, on `dev`) made `_copper_entry` leave such an entry out, as the KiCad and
Altium frames do; its test calls `model_pads` directly. c0403 adds the regression through the pass that
crashed: `test_zero_size_pads_do_not_stop_the_shadowed_rule_pass` places an SMD and a plated circular pad of
size 0 beside two overlapping clearance rules. With `padpath.py` of `75f9e995^` the test raises the same
`ValueError`; on this branch it returns one `rules.shadowed`. A private rerun of `fenolite check` on the
imported project at 1169f10d exits 5 instead of 1.

## F2: class minimums over custom rules

`dsl.convert._rules` writes a class minimum at priority 1, the highest, so that it governs the board minimum
(`docs/dsl.md`, "Class over board"). It therefore also governs every `rule()` of its class without
`priority=`. Changing the priority would change what every existing design checks, so the behaviour stays;
what was missing is the statement where a script author reads. The docstring of `minimum()` and the guide
page `board-insulation` now say it and name `precedence("specificity")`, which gives the more specific
two-sided rule the higher priority. `test_class_minimum_governs_a_custom_class_rule_until_specificity`
proves both orders and the `rules.shadowed` message.

## F3, F4: exceptions inside one part

No code is wrong: a selector `ref & item("pad")` on both sides matches every pad pair of the part, and a pin
on no net gets KiCad's `unconnected-(...)` net in `Default`. The guide page shows the per-domain form and how
to reach a no-connect pad. `tests/unit/checks/test_insulation_rule_scopes.py` resolves the page's selectors
with `ClearanceResolver` on an authored design of two domains and one part.

## F7: plans of other projects

`cli.plans.prune` counted every plan of the state folder against `PLAN_KEEP` = 16, so 16 dry runs of any
project on the machine dropped a plan under review. The count is now per working folder (the `cwd` each plan
records), with `PLAN_KEEP_ALL` = 128 plans and `PLAN_BYTES` in all as the machine's bound. A plan whose record
cannot be read counts only against the bound in all. `test_other_projects_do_not_drop_a_plan_under_review`
fails on the old `prune` and passes now. Pinning a plan was not added: `FENOLITE_STATE_DIR` already gives a
long review a store of its own, and the contract text now says so.

## F8: Specctra clearance order

`backends/specctra/dsn.py::_lower_rules` combined every clearance rule by maximum and kept a class's own
clearance as a floor for its self rule. KiCad applies the governing rule (`H-K-DRU-ORDER`), so the file
asked more than KiCad and Freerouting could not leave pads that KiCad accepts. Now:

- Clearance rules are taken in `rule_precedence` order (`dsn._precedence`, the same sort key, because
  `backends` may not import `checks`), and the last rule covering a class pair sets its `class_class`.
  Board-wide rules stay floors of the default and of every class.
- A governing self rule may lower its class. The class's previous value (its clearance, raised by
  board-wide rules) is kept against each other written class through `class_class`, unless a rule
  governs that pair. With nets without a class in the file, which would take the lower value against the
  class, the floor stays with `specctra.rule-widened`; so does a board-wide rule above the self value.
- Findings stay in the design's rule order. Width rules are unchanged.

Two expectations of `test_dsn_rules.py` follow from the new order and are updated, with reasons:
`test_class_class_self_pair_by_rule_order` relied on the design's order between two rules of equal
priority; KiCad orders them by name, so the test now gives the tighter rule priority 1 to keep its meaning,
and its "loose" case asserts the lowered class with the kept pairs. The test of pairs combined by maximum
keeps its assertions under a new name (the larger rule is also the governing one there).
`tests/unit/backends/specctra/test_dsn_rule_order.py` (6 tests) fails on the old code. No Freerouting run
backs the new rows of `docs/formats/specctra/dsn.md`: they are `INFERRED`.

## F9: copper against holes

`check_copper` judged holes against cut-outs and against each other, never against copper. The new pass
uses the holes of `_holes()` (with net, part and layer span added), a spatial index per copper layer and an
exact gap to the hole's wall. The value in force is `ClearanceResolver.hole()`: the last `hole_clearance`
rule that selects the pair, else `DesignRules.min_hole_clearance`, read by the KiCad rules source from
`board.design_settings.rules.min_hole_clearance` (`docs/formats/kicad/project.md`, `INFERRED`: the
template's hole minimum and hole-to-hole minimum are both 0.25 mm, so which key KiCad applied was not
probed). The board minimum is no floor over a rule (`H-K-PRO-MIN-RULE-3`). A pair already reported as a
short or a clearance finding is left out, as KiCad reports one violation per item pair (`H-K-DRU-KIND-2`).
The finding is not waivable, like `copper.edge-clearance`. Altium documents give no board minimum, so only
their `hole_clearance` rules apply.

The result dataclasses gain `hole_clearance` and `hole_clearance_judged` in `copper_check`, so the build,
check, render and view schemas are regenerated, `schemas/frozen-v0.json` included (the keys are additive).
`test_build_preserve_command.py::test_a_hole_over_a_part` drills a hole through both pads of a resistor:
KiCad reports that too, so the test now builds with `--copper-check warn` and asserts the two findings.
`route`, `tidy`, `place` reuse and the placement checks call `check_copper` without the value and do not
judge holes yet.

## F10, F6: copper below the governing track width

`checks/widths.py::track_width_findings` judges each track and arc against the `min` of its governing
`track_width` rule (`rule_precedence`, `selector_matches` on the copper check's subjects, layers, `ignore`
silences). The board-setup `min_track_width` is no floor over a rule (`FLOOR_OVER_RULES` is empty for
9.0.9 and 10.0.6). One finding per net and rule. The KiCad build guard reports `copper.track-width` and
treats it as its other copper errors (`--copper-check warn` makes it a warning); the Altium guard reports
it as a warning, as it does clearance. `route` judges only the copper the router added and reports
`route.width-below-minimum` (error) from its own code table, so no write is planned; its hint names
`--router-option fanout=off` for Freerouting. Copper that no rule selects is not judged, no width tolerance
is applied (none is recorded), and `fenolite check` leaves width to KiCad's DRC.

Found on 2026-11-05: the Altium writer sets each `Width` rule's `MINLIMIT` to the narrowest copper it writes
(`pcbdoc.py` `_class_rules`, c0038), not to the design's minimum, so an Altium build never reports narrow
copper. That is outside F10 and is listed as a follow-up.
