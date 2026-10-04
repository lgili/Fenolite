# Design: c0054 — design-rule minimums in the design script

## Context

- c0011 left the script without a rule constructor (its Open Question "Custom rules in the DSL"), and
  `dsl.convert.to_model` writes `RuleSet(id=key_id("rules"))` with no rule.
- The path below the DSL is complete and oracle-proved:
  - `model.rules.Rule` and `RuleSet` (c0004), in `rules.json` of the canonical form;
  - `backends.kicad.lowering.lower_rules` (c0018): `Design.rules` → `<name>.kicad_dru`, rule names
    `fenolite_<priority>_<slug>`, priority 1 written last so that it governs (`H-K-DRU-ORDER`);
  - `lowering.lower_minimums` and `class_conflicts` (c0026): board-wide rules → the minimums of
    `board.design_settings.rules` in `<name>.kicad_pro`, with the warnings
    `kicad.project.class-shadowed`, `kicad.project.below-floor` and `kicad.project.rule-below-minimum`;
  - `backends.kicad.triad.write_triad`, which `lens.build.build_design` calls, runs both;
  - `lens.preserve.merge_rules` (c0019): a rebuild writes Fenolite's rules first and keeps the user's
    rules, dropping old rules whose name starts with `fenolite_`;
  - `checks.clearance`, `placement.legality` and the copper guard already read `Design.rules` or the
    written texts.
- Observed at proposal time (2026-10-04, `kicad-cli` 10.0.6, macOS) with a prototype of Decision 1 on
  the routed blink (`examples/blink_routed/design.py`, built with its script copper):

  | minimums | `pcb drc` violations of the kind |
  |---|---|
  | none | none |
  | board `track_width` 0.4 mm | 7 `track_width` (the 0.3 mm tracks) |
  | board 0.25 mm, class `PWR` 0.6 mm | 4 `track_width`, all on `GND`, naming `fenolite_1_min_track_width_pwr` |
  | board `via_diameter` 0.7 mm | 7 `via_diameter` |
  | board `via_drill` 0.4 mm | 7 `drill_out_of_range` |
  | board `clearance` 1 mm | 38 `clearance` |
  | board 0.15 mm, class `PWR` 1 mm | 7 `clearance` |

  So no writer changes: the change is a constructor, a conversion and a proof.
- The Altium PCB document (c0038) writes Clearance, Width and Routing Via Style rules from the net
  classes plus `All` rules with Fenolite's defaults; it never reads `Design.rules`.

## Goals / Non-Goals

**Goals**

- One DSL call that declares clearance, track-width and via-size minimums for the board and per class.
- The minimums reach the model, the canonical JSON and the KiCad files, and `kicad-cli pcb drc`
  enforces them.
- The Altium build reports that it does not carry them.

**Non-Goals** (v0.2a unless stated): severities other than `error` and project `rule_severities`
(v0.2b); `opt` and `max`; layers; selectors other than the board and one class; custom expressions;
differential pairs; length matching; resolving class values against board minimums; minimums in the
Altium PCB document; new examples.

## Decisions

1. **One method, `design.rules.minimum(...)`, with one keyword per rule kind and `netclass=`.**
   It mirrors `design.rules.netclass(name, *, clearance, track_width, via_diameter, via_drill, nets)`:
   the same keyword names, the same unit forms (`as_nm`), `DslError` at the call. The six keywords are
   the six model kinds, so no kind of the model is out of reach; `hole_size` and `edge_clearance` cost one
   tuple entry each, are lowered by c0018 and c0026, and belong to any fab minimum set.
   - Rejected: `design.rules.rule(kind, *, min, max, selector…)`, a general constructor over c0018's
     selector algebra. It needs a DSL form for selectors, names and priorities, and the script would
     own conflicts between rules. That is the v0.2a rule constructor; `minimum()` does not block it.
   - Rejected: keywords on `design.board(...)`. Board minimums would fit, class minimums would not.
   - Rejected: extending `netclass()` with `min_*` keywords. A class value (what a router uses) and a
     minimum (what the check refuses) would share one call and be confused.
2. **Names, ids and priorities are fixed by the scope.** Board minimum: name `min_<kind>`, key
   `rule:<kind>`, priority 0. Class minimum: name `min_<kind>_<class>`, key `rule:<kind>:<class>`,
   priority 1. `lower_rules` writes priority 0 first and priority 1 last, and KiCad applies the last
   matching rule, so a class minimum governs its class whether it is above or below the board minimum.
   `lower_minimums` then returns the least of both as the board-setup minimum, so the floor never
   hides a lower class minimum.
   - Rejected: user-chosen names and priorities. Nothing in v0.1 needs them, and fixed keys keep ids
     independent of call order.
3. **A class must be declared before its minimum.** The error then points at the `minimum()` line.
   - Rejected: checking in `to_model`. The script would fail far from the cause.
   - `Default` is not special: a script that wants a minimum for unclassed nets uses a board minimum.
4. **No conflict resolution.** A board `clearance` minimum governs over a class clearance in KiCad
   (`H-K-PRO-MIN-CLASS`); c0026 already warns (`kicad.project.class-shadowed`) and names the fix, a
   class minimum. `docs/dsl.md` says so. Fenolite changes no value on the user's behalf.
5. **Altium: report, do not carry.** `lens.altium._not_lowered` adds one `altium.not-lowered` info with
   `where` = `design-rules`. The existing `where` = `rules` is taken by the net-class message, which is
   filtered out when the PCB document is written; a new `where` keeps this info in both cases.
   - Rejected: mapping minimums onto the `Rules6` records. The writer derives each rule's limits from
     the class value and the written copper so that the document's own copper never breaks them; a
     minimum above the copper contradicts that, and the result needs an Altium acceptance run. It also
     edits `pcbdoc.py` while c0053 works on the same path.
6. **Deltas.** `design-dsl` "Net classes in the DSL" and "DSL to model", and `design-model` "Identifier
   derivation", are MODIFIED from the living text (checked on `a2ec22b`); no active change modifies them.
   If c0053 modifies one of them and is archived first, this change's delta is rebased on its text.

## Files and public API

| file | change | public API |
|---|---|---|
| `src/fenolite/dsl/design.py` | edit | `MINIMUM_KINDS`, `MinimumSpec(kind, netclass, min)`, `Rules.minimum(...)`, `Rules.minimums` |
| `src/fenolite/dsl/convert.py` | edit | `KEYS["rule"] == ("rul", "rule:<kind>[:<net class>]")`; `to_model` fills `RuleSet.rules` |
| `src/fenolite/lens/altium.py` | edit | `_not_lowered` adds the `design-rules` info |
| `tests/unit/dsl/test_minimums.py` | new | DSL, conversion, ids |
| `tests/unit/lens/test_build_minimums.py`, `tests/unit/cli/test_build_minimums_command.py` | new | built `.kicad_dru`, `.kicad_pro`, `rules.json`, rebuild, Altium report |
| `tests/kicad/build/test_script_rules_oracle.py` | new | the oracle cases |
| `docs/dsl.md`, `docs/design-model.md`, `docs/altium.md`, `docs/hypotheses.md`, `CHANGELOG.md` | edit | — |

No new module, no schema change, no CLI change, no new issue code.

## Sources registered by this change

None. The facts used are registered: S-0010 and S-0038 (KiCad PCB editor manuals, custom rules).

## Hypotheses registered by this change

| id | claim | test | criterion |
|---|---|---|---|
| H-K-DSL-MINIMUM | The minimums a script declares with `design.rules.minimum` are enforced by `kicad-cli pcb drc` on the built project, for the board and per net class, on targets 9 and 10 (S-0010, S-0038; builds on `H-K-DRU-KIND`, `H-K-DRU-COND`, `H-K-DRU-ORDER`, `H-K-PRO-MIN-KEYS`) | `tests/kicad/build/test_script_rules_oracle.py` | per case of `kicad-oracle` "Script rule minimums are enforced by kicad-cli": the breaking build has a violation of the case's type and the respecting build has none |

The id collides with no row of `docs/hypotheses.md` and no active change (searched on 2026-10-04).

## Evidence level per behaviour

| behaviour | level before merge |
|---|---|
| DSL validation, conversion, ids, canonical JSON | unit tests |
| `.kicad_dru` text and `.kicad_pro` minimums of a build | unit tests over c0018 and c0026 code, which is `KICAD-VERIFIED (9.0.x, 10.0.x)` |
| `kicad-cli` enforces the built minimums (`H-K-DSL-MINIMUM`) | `KICAD-VERIFIED (10.0.x)` from the local 10.0.6; 9.0.x from the pinned image if present, else from the `kicad-9` job |
| Altium report | unit tests; no file changes |

The `build` envelope's evidence does not change: it already combines `lowering.EVIDENCE` and
`pro.EVIDENCE`.

## Budget

| part | days |
|---|---|
| DSL, conversion, unit tests | 0.25 |
| build tests, Altium report | 0.25 |
| oracle test | 0.25 |
| docs, registers, changelog | 0.25 |
| total | 1.0 |

## Risks / Trade-offs

- [A board clearance minimum silently lowers a class clearance] → c0026's warning is shown by `build`;
  `docs/dsl.md` states the rule and the fix.
- [A class name with a quote or a glob character] → `lower_rules` refuses it
  (`rules.unsupported-selector`); the build fails with that issue. No new check in the DSL.
- [The copper guard or the legality check now sees rules in script builds] → they already handle model
  rules; the fast suite covers it.
- [c0053 edits the same files] → the edits are one method, one helper and one block; see Decision 6.
- [`minimum()` is too narrow for v0.2a] → the general constructor is additive: `minimum()` stays as its
  shorthand.

## Migration Plan

Additive. A script without `minimum()` builds the same bytes. To roll back, remove the method, the
conversion helper, the key row and the Altium block.

## Open Questions

- **Name.** `minimum` (default) or `limits`/`rule`? The default matches c0026's "board-setup minimums".
- **Altium severity.** The not-carried report is an `info` (`altium.not-lowered`), as every other
  not-lowered item. A `warning` would need a new code; the default keeps the info.
- **Use in c0025.** Whether `board_40parts` declares minimums is c0025's choice; this change does not
  edit it.
