## Context

- **The gap (B4 of the dogfood buck board).** The board was built through Fenolite's public API, with a fab rule set in `Design.rules`, and written with `write_triad`.
  - c0018 wrote the rules to `.kicad_dru`.
  - c0010's synthesis kept the template values of `board.design_settings.rules`, and `kicad-cli` reported items that the rule set allows.
  - The report names "hole 0.3 mm, clearance 0.2 mm". The template's `min_through_hole_diameter` is 0.3 mm, but its `min_clearance` is 0. The 0.2 mm clearance is the `Default` class value, which c0010 lowers from a model class named `Default`.
- **Documented semantics.** The 10.0 manual (S-0038, Board Setup, sections Constraints and Net Classes, read on 2026-10-02) says that the Constraints minimums are absolute: no rule may override them, and a class value below a minimum is raised to it.
  - `docs/formats/kicad/rules.md` records the floor as `INFERRED` under `H-K-DRU-KIND`. c0010 measured it for `min_clearance` against a class (`H-K-PRO-FLOOR`, `KICAD-VERIFIED (9.0.x, 10.0.x)`); the other floors stayed `INFERRED`.
  - The part of the manual read for this design does not say how a custom rule and a net-class value combine when both are above the minimums. The 9.0 page (S-0010) is read by task 1.2.
- **Template values** (packaged templates; the 10 template is the 10.0.6 GUI save, S-0020, and the 9 template is derived from it, c0010 Decision 5). `board.design_settings.rules` holds 19 members.
  - The five that model kinds reach: `min_clearance` 0, `min_track_width` 0.2, `min_via_diameter` 0.5, `min_through_hole_diameter` 0.3 and `min_copper_edge_clearance` 0.5 (mm).
  - The others: `min_hole_clearance`, `min_hole_to_hole`, `min_via_annular_width`, `min_microvia_diameter`, `min_microvia_drill`, `min_connection`, `min_groove_width`, `min_silk_clearance`, `min_text_height`, `min_text_thickness`, `min_resolved_spokes`, `solder_mask_to_copper_clearance`, `max_error` and `use_height_for_length_calcs`.
- **Census** (observed on 2026-10-02 with a JSON reader over the cached `project` rows of c0010's corpus; key names and counts only, not normative):
  - At tag 10.0.6, 19 of 35 project rows hold all five keys (18 of them with `meta.version` 3).
  - At tag 9.0.9.1, 10 of the 17 rows that differ from 10.0.6 hold them (9 with version 3).
  - The 2 demo rules files hold 16 rules, none without a condition.
- **Today's code** (c0010 and c0018 archived).
  - `lowering.FLOOR_KEYS` maps four `NetClass` fields to floor keys. `lower_netclass` warns `kicad.project.below-floor` against `project_floors` of the project being written: the template on synthesis, the existing file on update.
  - `synthesize_project` and `update_project` keep every key except the classes and patterns. `write_triad` calls them and `lower_rules`.
  - `rulemap.normal_form` turns `via_drill` into `hole_size` with `item_kind via` and an `all` B side into `None`. `rulemap.rule_order` puts priority 0 first, then descending priority, ties by name and id; the later rule governs (`H-K-DRU-ORDER`, `KICAD-VERIFIED`).
  - `lower_rules` writes every modelled rule, board-wide ones included, as a custom rule.
  - `model.rules` has six kinds, `priority` 0 for unset and 1 for highest, the selector `all` and `layers` empty for every layer.
  - c0011's DSL has no rule constructor in v0.1 (its Decision 3), so rules reach `write_triad` only through the model API.
  - c0012 Decision 10 adds project keys with an ADDED requirement that takes precedence over c0010's requirements for its keys and extends the closed code table.
- **Environment.** KiCad 10.0.6 runs locally on macOS. 9.0.9 runs in the pinned image of the `kicad-9` job (S-0029).
- **Constraints.** Standard library only. `backends.kicad` modules import `model`, `geometry`, `backends.base` and their own package (`package-layering`). Facts come from the manual, GUI saves and `kicad-cli` runs; no KiCad source file is read for this change.

## Goals / Non-Goals

**Goals:**
- Every modelled rule of a fab rule set takes effect in `kicad-cli` 9.0 and 10.0, whatever the template's minimums.
- The written minimums are a function of the model's rules. Written again from the same rules they do not change, and nothing is invented on read-back.
- Every remaining case where KiCad does not apply a value that the model asks for is reported, on the targets where it was measured.
- Every claim is proved on both majors with a canary.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- Any change to what c0018 writes to `.kicad_dru`.
- Severity overrides (`rule_severities`, c0020).
- Reasoning about which items a selector covers on a given design.

## Decisions

1. **Board-wide rules stay custom rules; the minimums are derived from them.** `lower_rules` is unchanged. Synthesis and update write the minimums that `lower_minimums` derives from the same rules.
   - The custom rules keep the model's priority semantics exactly. The minimums only stop the template from overriding them.
   - The two statements cannot disagree in effect. By Decision 3, each written minimum is at most the `min` of every rule that can govern an item of its kind. Under the documented semantics (S-0038) the minimum then never overrides the `min` of a rule that governs an item; under the opposite semantics, custom rules override it anyway.
   - A Board Setup edit of a managed key is replaced on the next write, with `kicad.project.minimum-replaced` (Decision 5).
   - Rejected: lowering a board-wide rule only to the minimum. This is KiCad's own practice (the 16 demo rules all carry a condition, Context), and it keeps net-class clearances above the floor. But after a read-back the rule is no longer in the model, unless every minimum is lifted into a rule (rejected in Decision 6). It also drops the rule's priority and severity, and needs MODIFIED deltas of c0018's "Fenolite lowers only the design's rules" and c0010's "Generated projects are coherent". Open Questions keeps it for a later change.
   - Rejected: a model entity for board minimums. It would be a second way to state what a board-wide rule already states.

2. **What board-wide means in the closed grammar.** `is_board_wide(rule)` holds when the normal form has `selector_a == Selector("all")`, `selector_b is None` and `layers == ()`.
   - `all` is allowed at the top level only (rules-model, "Closed selector grammar"); a `selector_b` of `all` becomes `None` in normal form; empty `layers` means every layer (rules-model, "Rule layers and lowered names").
   - A rule that lists every copper layer, or an `or` of every net, is not board-wide. Fenolite does not reason about coverage.
   - A `via_drill` rule on `all` is not board-wide: its normal form selects vias only, while `min_through_hole_diameter` is named for every through hole, pad holes included (`INFERRED` from the key name; the part of S-0038 read does not list the hole minimums).
   - Rejected: "a rule that selects every item of the design". It needs the design's nets and layers, and a net added later in KiCad breaks it.

3. **The written value is the least `min` of the rules that can govern.** Per kind, the governing board-wide rule is the last board-wide rule of that kind in `rulemap.rule_order`. A key is written only when that rule has severity `error` and a `min`. Its value is the least `min` among the governing rule and the later rules of the same kind.
   - Every item of the kind is governed by the governing rule or by a later rule (`H-K-DRU-ORDER`). The least of their `min` values is therefore the lowest value that the rule set allows anywhere: the board minimum of the rule set.
   - Rules before the governing rule never govern any item, because the governing rule matches all their items and comes later. They do not count.
   - A later rule without a `min` (a `max` only) adds nothing. The items it governs keep the written minimum as their only minimum, which is KiCad's floor behaviour and is not reported.
   - Example: a board-wide `hole_size` rule of 0.3 mm (priority 0) and a `via_drill` rule on `all` of 0.2 mm (priority 1) give `min_through_hole_diameter` 0.2. Pad holes are still held to 0.3 mm by the custom rule; vias may be 0.2 mm.
   - A governing rule of severity `warning` or `ignore` writes nothing (`kicad.project.minimum-kept`). A minimum has no severity, so writing it would report the rule's items as errors. A governing rule with no `min` leaves no minimum to write.
   - Rejected: the governing rule's own value. A later, narrower rule with a lower `min` would then be overridden by the minimum (S-0038), which is the disagreement this change must avoid.
   - Rejected: the least `min` of every rule of the kind, also without a board-wide rule. It would relax the minimum for items that no rule covers, where the template value (KiCad's default) is still in force.
   - Rejected: also lowering from class values. Classes belong to c0010, and a class below a written minimum keeps its `kicad.project.below-floor` warning.

4. **The mapping is per target major.** `MINIMUM_KEYS[9]` and `MINIMUM_KEYS[10]` hold the same five keys: names from the 10.0.6 GUI save and the derived 9 template, with the census at both tags as supporting data. The oracle settles each key on each major (`H-K-PRO-MIN-KEYS`); a key refuted on a major leaves that major's entry (Decision 9).
   - c0010's `FLOOR_KEYS` (class fields) is unchanged and agrees with this table: `via_drill` maps to `min_through_hole_diameter` there too.
   - Not mapped: the micro-via minimums (no kind targets micro-vias) and the other keys of the Context, which no kind reaches (Decision 8). They are kept verbatim.
   - Rejected: a key for the raw kind `via_drill`. KiCad has no through-hole minimum for vias alone.

5. **The minimums are written inside synthesis and update, before the classes.** `synthesize_project` runs: template, `meta.filename`, minimums, floors, classes, class conflicts, patterns. `update_project` runs: parse, version checks, target-9 gate, minimums, floors, classes, class conflicts, patterns.
   - `current` is the existing value of each key, or the target template's value when the key is absent. KiCad's default for an absent key equals the template value, because the empty-template save filled them in (c0010 Decision 4); this is `INFERRED`.
   - The step reads `current` without adding issues. c0010's `project_floors` then reads the written values, so an inexact value of one of its four floor keys is reported once, by `kicad.project.inexact-value`, and a replaced value is named by `kicad.project.minimum-replaced`.
   - An equal value (in nm) keeps its text. A new value is the exact millimetre text of `lowering.millimetres`.
   - A missing key is appended to the rules object in the order of the table, and a missing parent object is appended to its own parent. A parent that is not an object raises `FormatError` with its pointer, because writing into it would destroy content.
   - Updates give the info `kicad.project.minimum-replaced` for each changed or added key. Synthesis gives none, because replacing template values is its purpose.
   - Without a written key the text is the one c0010 gives. c0010's scenarios and probe outcomes therefore stand (its bench holds only the scoped canary rule), and so does c0012's scenario "Nothing to set".
   - Rejected: a post-step on the text inside `write_triad`, c0012's form for its keys. The floors that c0010 passes to `lower_netclass` would then be the old values, and `kicad.project.below-floor` would be wrong in both directions.
   - Rejected: writing a key only when it is absent. The template or a Board Setup value would keep overriding the rules.

6. **Minimums are not read back into rules.** `pro.project_minimums(data)` reads them, and `apply_project` leaves `Design.rules` alone.
   - The rules come back from `.kicad_dru` through c0018's `read_rules`. The next write recomputes the same minimums: Decision 3 depends only on kinds, selectors, layers, `min` values, severities and order, which `read_rules` keeps in normal form.
   - A project without a board-wide rule keeps every minimum it holds, on update too, so Board Setup edits survive.
   - Rejected: lifting every minimum into a board-wide rule. The template defaults would become user rules, every read design would gain five rules, and the next write would emit them as custom rules.
   - Rejected: lifting only values that differ from the template. A user value equal to the default would vanish, and defaults may change between versions.

7. **Reports, all warnings or infos.**

   | code | severity | when |
   |---|---|---|
   | `kicad.project.minimum-replaced` | info | an update writes a minimum that is absent from the file, is not a number there, or differs in nanometres |
   | `kicad.project.minimum-kept` | info | the governing board-wide rule has severity `warning` or `ignore`, or no `min` |
   | `kicad.project.rule-below-minimum` | warning | a rule's `min` is below a minimum that Fenolite does not write, on a target where minimums govern custom rules |
   | `kicad.project.class-shadowed` | warning | a class clearance is above the governing board-wide clearance rule, on a target where custom rules govern class items |
   | `kicad.project.default-over-rule` | warning | the `Default` class, which the model does not set, is above the governing board-wide clearance rule, on a target where class clearances govern above custom rules |

   - `rule-below-minimum` answers c0010's open question on rules below a floor. It is gated per key and major by `FLOOR_OVER_RULES` (`H-K-PRO-MIN-RULE`).
   - Class clearances against a board-wide clearance rule have two possible outcomes, and `H-K-PRO-MIN-CLASS` picks one per major (`RULES_OVER_CLASSES`). `lowering.class_conflicts` runs after the classes are written, on every class entry of the project.
     - If KiCad applies a custom rule without a condition to every item, a larger class clearance is silently lost. This is the case of the dogfood board: power classes plus a fab clearance rule. `class-shadowed` names each such class, except a `Default` entry that the model does not set (the rule is meant to govern those nets), and except a class that a later clearance rule on `netclass <name>` with at least its value restores.
     - Otherwise the class value governs its nets above the rule. A model class asked for that, but the template's `Default` (0.2 mm) did not: it would keep every unclassed net above the fab rule, which is B4's "clearance 0.2 mm". `default-over-rule` names it, and its hint says that a model class `Default` lowers it (c0010).
   - Only clearance is checked against classes. c0010 proved that DRC enforces class clearances (`H-K-PRO-NETCLASS`); class track and via values were never measured as DRC limits.
   - A class below a written minimum keeps c0010's `kicad.project.below-floor`, which now compares with the written values (Decision 5).
   - Rejected: unconditional warnings, which would be false alarms on a major where custom rules go below a minimum, or where classes and rules combine. Rejected: errors and `LossyWriteError`. Nothing is lost from the files; c0010 made the same choice for `below-floor`.

8. **No new rule kinds.**
   - The five kinds reach what B4 names (the hole minimum, and clearance through the `Default` class) and the other template minimums that a rule set with smaller values runs into: tracks 0.2, vias 0.5 and copper to edge 0.5 mm.
   - The other minimums (annular width 0.1, hole to hole 0.25, copper to hole 0.25, micro-vias) stay editable in Board Setup, and updates keep them verbatim.
   - A new kind changes `RuleKind`, the `rules.json` schema, design-model "Model layers for v0.1" (which c0012 modifies), the kind and limit tables of `rulemap`, the reader and the kind proofs of `H-K-DRU-KIND` on both majors: about 3 days, better placed in v0.2a.
   - Rejected: `annular_width`, `hole_to_hole` and `hole_clearance` kinds now. Rejected: kinds that only set a minimum; they would have no custom-rule form, which breaks Decision 1.

9. **Measured tables, pinned to the probe files.** `FLOOR_OVER_RULES` (key to majors), `RULES_OVER_CLASSES` (majors) and `MINIMUM_KEYS` (major to kinds) follow the probe outcomes of Decision 10. `tests/unit/backends/kicad/test_lowering_minimums.py -k tables` compares them with `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, as c0018 does for `SELECTOR_SUPPORT`.
   - Until task 5.2 runs, the shipped values are the claims of the hypotheses: every key on `{9, 10}` for `FLOOR_OVER_RULES` (S-0038), `{9, 10}` for `RULES_OVER_CLASSES`, and the full table for `MINIMUM_KEYS`. The oracle tests assert the outcome that the tables give, so a measurement that disagrees fails until the table follows it, as c0010 did for `pattern_matches`.
   - A measurement that differs changes the table and adds a `-2` successor of the hypothesis (c0014 Decision 5).
   - c0029 (copper check, proposed in parallel) reads `RULES_OVER_CLASSES` and `FLOOR_OVER_RULES["min_clearance"]` by these names, with the same shipped defaults, so the names are a contract with it.
   - The bench measures `FLOOR_OVER_RULES` on board-wide rules only. Applied to a rule with a condition, as `kicad.project.rule-below-minimum` and c0029's resolver apply it, the table's value is `INFERRED` from S-0038 ("no rule may override the minimums"); c0029's resolution row "a floor above a rule", whose rule selects its probe nets, measures the clearance case.
   - Rejected: per-target constants without probes. They could not detect a later image with other behaviour.

10. **Oracle bench, scoped canary and four runs.** A clean DRC proves nothing (`H-K-TOK-RULES-SILENT`), so every run carries a canary. `tests/_minimum_bench.py` builds the bench through the model, and `write_triad` writes it.
    - Probe items: two 0.25 mm tracks with a 0.15 mm gap (`clearance`), a 0.15 mm track (`track_width`), a via of 0.45 mm diameter and 0.24 mm drill (`via_diameter`), a via of 0.6 mm diameter and 0.25 mm drill (`hole_size`), and a 0.25 mm track whose copper edge is 0.35 mm from the board edge (`edge_clearance`). Every item is at least 4 mm from other copper, and at least 0.05 mm from both limits.
      - The via annular widths, 0.105 mm and 0.175 mm, stay above the template's 0.1 mm. The 0.24 mm drill of the `via_diameter` probe is below the template hole minimum, so the template runs also give it a `drill_out_of_range`, which its judge ignores; it is above the 0.2 mm of the lowered runs.
      - The edge distance stays between 0.2 and 0.5 mm whether KiCad measures to the outline's centre line or to its edge.
    - A row of class HV (clearance 2 mm) beside a `GND` track 1.0 mm away. A model class `Default` with clearance 0.05 mm keeps every probe pair free of class violations, whatever KiCad does with classes.
    - Five board-wide rules of severity `error` and priority 0: `clearance` 0.1, `track_width` 0.1, `via_diameter` 0.35, `hole_size` 0.2 and `edge_clearance` 0.2 mm.
    - The canary of c0010's bench: a 3 mm clearance rule on `net CANARY_A` with priority 1, written last, and a `CANARY_B` track 0.75 mm away. An unconditional canary written first would be governed by the board-wide clearance rule written after it; written last, it would flag every probe pair.
    - Runs per target:
      - `keys-template`: no board-wide rule, template keys, `min_clearance` 0.2. The template's 0 cannot block anything.
      - `keys-lowered`: the five keys set below the items by the test.
      - `rules-template`: the rules, with the keys reset to the template values and `min_clearance` 0.2.
      - `rules-lowered`: the triad as written.
    - Probes `pro-min-<run>-<kind>-t<target>`, `pro-min-class-t<target>` (HV in `rules-lowered`) and `pro-min-class-control-t<target>` (HV in `keys-template`), each `present`, `absent` or `inconclusive` (canary missing). Target-10 runs run on major 10, target-9 runs on 9 and 10: 22 probes per target. Pure judge functions are tested on authored reports, as c0010 does.
    - Violations are matched by item uuid and by the type that c0018 observed for each kind (`clearance`, `track_width`, `via_diameter`, `drill_out_of_range`, `copper_edge_clearance`).
    - Stop rule: a `present` outcome in `rules-lowered` means the written project does not let a rule take effect. The change stops until that is explained.
    - Rejected: reusing c0018's rules bench. Its unconditional canary and `{}` project cannot test a project file. Rejected: judging by exit code.

11. **One ADDED requirement, and two MODIFIED deltas that open an exception path.** "Project files carry the board-setup minimums" takes precedence, for the five keys, over the template-value and keep rules of c0010's "Project files are synthesised and preserved", and extends c0010's closed table "Project issue codes", as c0012 does for its keys.
    - Those living texts state the opposite without an exception: every other key keeps its template value, an update keeps every other key's value and spelling, and the table is closed. So this change MODIFIES both, copying the living texts in full and adding one sentence each: another requirement of `kicad-file-backend` MAY take named keys out of those rules, or add rows to the table, when it names the requirement. The ADDED requirement names both.
    - Archive order: c0010 is archived (2026-10-02), so the bases are the living texts. No other active change modifies either requirement. c0012 archives later and uses the same exception paths for its own keys (`pcbnew.page_layout_descr_file`, `text_variables`) and codes, so neither change rebases on the other.
    - No requirement of c0011 is modified, so none of the six that c0019 modifies is touched.
    - Rejected: ADDED precedence alone (after archive, the living texts would still state the opposite with no exception). Rejected: moving the whole minimum rule into the MODIFIED text (one long requirement for two concerns, copied again by any later change of it).

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/kicad/lowering.py` (c0018, c0010; extended) | `MINIMUM_KEYS: Mapping[int, Mapping[RuleKind, str]]`; `FLOOR_OVER_RULES: Mapping[str, frozenset[int]]`; `RULES_OVER_CLASSES: frozenset[int]`; `is_board_wide(rule: Rule) -> bool`; `lower_minimums(ruleset: RuleSet \| None, *, target: int, current: Mapping[str, Nm], issues: list[Issue] \| None = None) -> dict[str, Nm]`; `class_conflicts(ruleset: RuleSet \| None, *, target: int, clearances: Mapping[str, Nm], model_names: Collection[str], issues: list[Issue] \| None = None) -> None` |
| `src/fenolite/backends/kicad/pro.py` (c0010; extended) | `MINIMUM_POINTER = "/board/design_settings/rules"`; `project_minimums(data: JsonObject, *, issues: list[Issue] \| None = None) -> dict[str, Nm]`; `synthesize_project` and `update_project` write the minimums and call `class_conflicts` (Decision 5); signatures unchanged |
| `src/fenolite/backends/kicad/proerrors.py` (c0010; extended) | five rows in `ISSUE_CODES` (Decision 7) |
| `src/fenolite/backends/kicad/__init__.py` | re-exports `project_minimums` and `lower_minimums` |
| `src/fenolite/backends/kicad/PROVENANCE.md` | rows for the minimum keys, the floors and the census |
| `tests/unit/backends/kicad/test_lowering_minimums.py` (new) | `lower_minimums`, `is_board_wide`, `class_conflicts`, the reports, and `-k tables` against the probe files |
| `tests/unit/backends/kicad/test_pro_minimums.py` (new) | synthesis, update, spellings, missing keys, `FormatError`, `project_minimums`, read-back, codes |
| `tests/unit/backends/kicad/test_pro.py` (c0010; extended) | census of the five keys per tag in the `FENOLITE_CENSUS_OUT` file |
| `tests/_minimum_bench.py` (new) | `bench_design(*, target: int, board_wide: bool = True) -> Design`; `KINDS`; `VIOLATION_TYPES: Mapping[str, str]`; `RUNS = ("keys-template", "keys-lowered", "rules-template", "rules-lowered")`; `KEYS_LOWERED: Mapping[str, str]` (key to mm text set by `keys-lowered`); `RAISED_CLEARANCE = "0.2"` (the `min_clearance` of the template runs); `item_uuids(design: Design, kind: str) -> tuple[str, ...]`; `judge_item(report: DrcReport \| None, *, kind: str, design: Design) -> str`; `judge_class(report: DrcReport \| None, *, design: Design) -> str`; `assert_loaded(outcome: str, case: str) -> None` |
| `tests/unit/test_minimum_bench.py` (new) | hermetic checks of the judges on authored report texts, and of the bench written with `write_triad` |
| `tests/kicad/project/_mincases.py` (new) | `run(name: str, target: int) -> Run`; `min_probes() -> dict[str, tuple[object, tuple[int, ...]]]` |
| `tests/kicad/project/test_minimums_drc.py` (new) | `test_keys`, `test_floor_over_rules`, `test_written`, `test_rules_over_classes` (`needs_kicad`, major-aware) |
| `tests/kicad/_probes.py` (c0017; extended) | registers `min_probes()` |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` (regenerated) | outcomes of the `pro-min-*` probes |
| `docs/formats/kicad/project.md`, `docs/formats/kicad/rules.md`, `docs/evidence/kicad-project.md` | fact rows, the section "Board-setup minimums", the floor row re-labelled, census counts |

Layering: `lowering` keeps its imports (`rulemap`, `dru`, `_json`, `proerrors`, `model.rules`, `model.circuit`), and `pro` already imports `lowering`. All stay inside `backends.kicad`, `backends.base` and `model`, as `package-layering` allows. No new module is created in `src`.

## Sources registered by this change

No new row: every fact comes from pages and runs that are already registered. S-0100 to S-0104 stay unused.

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0038 (extended) | https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html#custom_rule_syntax (the whole page, as registered) | GPL-3.0-or-later or CC-BY-3.0-or-later (stated on the page) | adds: Board Setup Constraints minimums are absolute, no rule may override them, and a class value below one is raised to it |
| S-0010 (extended) | https://docs.kicad.org/9.0/en/pcbnew/pcbnew.html | GPL-3.0-or-later or CC-BY-3.0-or-later (stated on the page) | adds: the 9.0 Constraints minimums and their role, as read by task 1.2 |

Also cited: S-0020 (the 10.0.6 GUI save and `kicad-cli` 10.0.6 runs), S-0029 (the pinned 9.0.9 image), S-0024 and S-0058 (the demo project rows of the census).

## Hypotheses registered by this change

The stem `H-K-PRO-MIN-` was assigned to this change. The existing row `H-K-PRO-MIN` (c0010, a minimal project file) is a different claim.

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PRO-MIN-KEYS | `kicad-cli` 9.0 and 10.0 read `min_clearance`, `min_track_width`, `min_via_diameter`, `min_through_hole_diameter` and `min_copper_edge_clearance` from `board.design_settings.rules` and apply them to items that no custom rule governs (S-0038, S-0010; names from the 10.0.6 GUI save, S-0020) | `tests/kicad/project/test_minimums_drc.py::test_keys` | per key: the probe item has its violation in `keys-template` and none in `keys-lowered`, and the canary fires in both, on 9.0.9 (target 9) and 10.0.6 (targets 9 and 10) |
| H-K-PRO-MIN-RULE | A board-setup minimum above the `min` of a board-wide custom rule governs: an item between the two values is reported (S-0038: no rule may override the minimums). For rules with a condition the same is `INFERRED` from S-0038, not measured here; `FLOOR_OVER_RULES` carries the measured outcome to them | `tests/kicad/project/test_minimums_drc.py::test_floor_over_rules` | per key: the probe item between the board-wide rule and the template minimum (`min_clearance` 0.2) has its violation in `rules-template`, the canary fires; on 9.0.9 and 10.0.6; each outcome sets `FLOOR_OVER_RULES` |
| H-K-PRO-MIN-WRITE | The project that Fenolite writes from board-wide rules lets the rule values take effect: no probe item between a rule value and the template minimum is reported (S-0038) | `tests/kicad/project/test_minimums_drc.py::test_written` | no probe item has its violation in `rules-lowered`, the canary fires; on 9.0.9 and 10.0.6 |
| H-K-PRO-MIN-CLASS | A custom clearance rule without a condition governs the items of a net class with a larger clearance, so the class clearance is not applied (no public statement found; S-0038 states only the floors and the order among custom rules) | `tests/kicad/project/test_minimums_drc.py::test_rules_over_classes` | the HV row (class 2 mm, gap 1.0 mm) has no violation in `rules-lowered` (board-wide 0.1 mm rule) and has its violation in `keys-template` (no such rule), the canary fires in both; on 9.0.9 and 10.0.6; the outcome sets `RULES_OVER_CLASSES` |

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Key names per target | KICAD-VERIFIED (10.0.x; GUI save) for 10; the 9 side INFERRED (derived template, c0010 Decision 5) until the 9.0.9 run, with the census as supporting data | `test_project_fixtures.py` (c0010), census of `test_pro.py` |
| The five keys are read and applied | KICAD-VERIFIED (9.0.x, 10.0.x) per key (`H-K-PRO-MIN-KEYS`) | `test_minimums_drc.py::test_keys` |
| A minimum governs a lower custom rule | KICAD-VERIFIED per key and major as measured, for board-wide rules of severity `error` (`H-K-PRO-MIN-RULE`); INFERRED (S-0038) for rules with a condition, which the bench does not hold, and for `warning` and `ignore` | `test_floor_over_rules` |
| The written project lets the rules take effect | KICAD-VERIFIED (9.0.x, 10.0.x) (`H-K-PRO-MIN-WRITE`) | `test_written` |
| Custom rules and class clearances | KICAD-VERIFIED (9.0.x, 10.0.x) as measured, clearance only (`H-K-PRO-MIN-CLASS`) | `test_rules_over_classes` |
| Board-wide definition, value choice, severity rule | mechanical (unit tests); the order rule rests on `H-K-DRU-ORDER` (KICAD-VERIFIED) | `test_lowering_minimums.py` |
| Writing, spellings, missing keys, unchanged text, read-back | mechanical (unit tests) | `test_pro_minimums.py`, c0010's `test_pro_synth.py`, `test_pro_update.py`, `test_write_triad.py` |
| Default of an absent key equals the template value | INFERRED (c0010 Decision 4) | none here |
| Tables follow the probes | mechanical | `test_lowering_minimums.py -k tables`, `tests/kicad/test_probe_results.py` |

No evidence constant is added: minimums create no `Provenance` (Decision 6), and the issues carry their own codes.

## Budget (6.5 working days)

| work | days |
|---|---|
| sources, hypotheses, provenance, format pages, census | 1.0 |
| `lower_minimums`, board-wide rule, value, codes | 0.75 |
| reports, `class_conflicts` and tables | 0.75 |
| writing in synthesis | 0.5 |
| writing in updates, read-back, c0010 regression | 0.75 |
| bench and hermetic judges | 0.75 |
| oracle on 10.0.6 | 0.75 |
| oracle on 9.0.9, probe files, tables pinned | 0.75 |
| closing | 0.5 |
| **total** | **6.5** |

c0010 planned 0.5 days for class lowering with its floor warning and 1.0 for its oracle. This change reuses c0010's codec, templates and bench pattern, but its lowering rules and its four runs per target are larger, hence the higher lines. Cut order:
1. The census counts of task 1.4 (supporting data only), −0.25.
2. `class_conflicts`, its two codes, `RULES_OVER_CLASSES` and `H-K-PRO-MIN-CLASS`, deferred with Open Question 1, −0.75.

Not optional: `lower_minimums`, the writing in synthesis and update, and the keys, rules and written proofs on both majors.

## Risks / Trade-offs

- [A major lets custom rules go below a minimum (`H-K-PRO-MIN-RULE` refuted)] → `FLOOR_OVER_RULES` loses that major and no false warning is given. The minimums are still written: harmless there, and Board Setup shows the rule set's values.
- [9.0.9 does not read a key of the derived template] → `MINIMUM_KEYS[9]` loses it with a `-2` successor of `H-K-PRO-MIN-KEYS`. That key is then neither written nor warned about for target 9.
- [A floor violation has another type than the custom-rule violation] → the judge reports `absent` or `different` and the test lists the types found on the item. Task 5.1 then adds the observed type to `VIOLATION_TYPES` and records it in `rules.md`.
- [`H-K-PRO-MIN-CLASS` holds] → every board-wide clearance rule silences larger class clearances in KiCad unless a rule on `netclass <name>` restores them. `class-shadowed` names the class and the fix. The rejected minimum-only lowering stays an open question.
- [`H-K-PRO-MIN-CLASS` is refuted] → the template's `Default` clearance keeps unclassed nets above a smaller board-wide clearance rule. `default-over-rule` says so, and a model class `Default` fixes it through c0010. A class clearance below the rule is not measured here; how KiCad combines the two then stays `INFERRED`.
- [Opaque rules, and user rules that c0019 keeps verbatim, are not seen] → such a rule below a written minimum is overridden without a warning. `project.md` states it, and a later check (c0013, c0029) can find it.
- [Micro-vias] → a board-wide `via_diameter` or `hole_size` rule below the micro-via minimums (0.2 and 0.1 mm in the template) is overridden for micro-vias, without a warning. No kind targets micro-vias (Open Question 2).
- [Board Setup edits of a managed key are replaced on the next write] → `kicad.project.minimum-replaced` names the old and new values. Keys without a board-wide rule are never touched.
- [Project-only classes, made in the KiCad GUI] → `class_conflicts` sees every class entry of the written project, so a GUI class above the rule is named by `class-shadowed` too; on a target where class values govern, only the `Default` entry is reported.
- [Overrun] → the cut order above.

## Migration Plan

- Additive code: new functions and tables in `lowering.py`, `pro.py` and `proerrors.py`, new tests, a bench and probes. The model, the schemas, `FileKind`, the CLI and the dependencies are unchanged.
- Designs without an `error` board-wide rule produce byte-identical projects, so existing triads, benches and probe files keep their outcomes.
- Existing projects keep their minimums until a design with a board-wide rule rewrites them.
- To roll back, remove the step from `synthesize_project` and `update_project`, the new functions, tables, codes, tests, probes and doc rows, and restore the rules.md floor row and the living texts of the two MODIFIED requirements.

## Open Questions

1. Should a later change lower `error` board-wide rules only to the minimums, the KiCad practice that keeps class clearances above the floor, with a marker that lets reading lift them back? Default: no. Revisit if `H-K-PRO-MIN-CLASS` holds and the rule on `netclass <name>` proves heavy for users.
2. Should board-wide `via_diameter` and `hole_size` rules also write `min_microvia_diameter` and `min_microvia_drill`? Default: no; they are kept verbatim.
3. Should `annular_width`, `hole_to_hole` and `hole_clearance` become kinds? c0031 also leaves `zone_connection` to the owner of "Rule kinds and limits", and c0030 expects that `min_silk_clearance` may be lowered later. Default: no kind in this change; all of them go to one v0.2a change with the model change of Decision 8, and the minimums stay editable in Board Setup.
4. Should rules that a higher-priority board-wide rule shadows be reported (they never govern)? Default: not here. It is a property of the rule set; `Design.validate()` or c0029 can own it.
5. Should `kicad.project.minimum-replaced` be a warning when it relaxes a value set in Board Setup? Default: info, because the rules are the authority for a managed key.
6. c0029 needs the clearance in force. Its proposal already takes `RULES_OVER_CLASSES` and `FLOOR_OVER_RULES["min_clearance"]` from this change and models the refuted case of `H-K-PRO-MIN-CLASS` as the larger of rule and class. Default: keep the names and defaults stable; a change to either table after merge is announced to c0029.
7. The report's "clearance 0.2 mm" is the `Default` class value. When `RULES_OVER_CLASSES` holds, a board-wide clearance rule already governs `Default` nets; when it does not, `default-over-rule` asks for a model class `Default` with the lower value (c0010). Should Fenolite lower the template's `Default` clearance by itself in that case? Default: no; the class is c0010's, and the warning names the fix.
8. No question of `batch_shared.json` concerns this change. c0010's question on a 9.0.9 GUI save is closed by its Decision 5 fallback, which this change inherits for the 9 key names.
