## Context

**Scope.** Part heights stated in a script and height limits over named rule areas, judged by `check`, `place` and `build`. The scope was part of c0113-placement-constraints until 2026-10-07; the maintainer's decision 3 of that day (after the review of the 26 proposals of v0.4) took it out: "Part height: taken out of c0113 into a change of its own, written after c0099 is on dev, one source of height".

**What exists** (read at `origin/dev` `9aba2dff` on 2026-10-07):

- *Model.* `fenolite.model.board.ComponentBody(kind, height, standoff=0, outline=(), layer="", model="", name="")`, an entity with the id prefix `bdy`, in `FootprintInstance.bodies` and `FootprintDef.bodies`. The living "Component bodies" (`design-model`) says: "The height of a part is the largest `height` of its bodies; a part without bodies has no known height", and: a KiCad build keeps the bodies of a design in `.fenolite/` only. No function computes that height; nothing reads it.
- *Where a body comes from.* Only from the Altium import (`backends/altium/adapter/bodies.py`). No call of `ComponentBody` is under `src/fenolite/dsl` or `src/fenolite/catalog`, and a definition read from a KiCad library holds none (c0121's design says the same and leaves "a height in a script" to a later change of the DSL).
- *Writing bodies.* c0121 (open on `dev`, part of `0.3.0`) writes extruded bodies into Altium documents on request (`--altium-bodies extruded`). `pcblib.body_problem` refuses a body of kind `model`, one with fewer than three outline points, one with a negative standoff and one whose height is not above its standoff; each is counted under the kind `body` of `altium.not-lowered`. The stored board of an Altium build holds exactly the bodies that were written, so that its round-trip check compares them.
- *The KiCad build.* `lens.build.build_design` places footprints from library definitions and merges the result with the existing board (`lens.preserve.merge_layout`). For a footprint that the board already holds, the merge keeps the node read from the board (`preserve.py`, the loop that appends `dataclasses.replace(node, component_id=…, pads=…)`), which has no body, so a body of the built footprint is dropped on a rebuild today. No test sees it, because no KiCad build has a body.
- *The script.* `dsl.to_model` gives the circuit, the rules and the library layer; placements travel beside it (`dsl.placements(design)`), and copper as intents (`dsl.copper(design)`). The footprints of the board are made by the lens.
- *Not on `dev`:*
  - c0099 (`codex/c0099-body-volumes`, implemented): `ComponentBody` gains `z_min`, `z_max` (a signed interval in the mounted-face frame, both or neither) and `projection_unknown`. Its "Component bodies" reads: "The outward height of a part is the largest authoritative upper bound of its known bodies (`z_max` when present, legacy `height` otherwise) … A part without known body extents has unknown height." `analysis/body_volumes.check_body_volumes(design, constraints)` judges volumes in space against `VolumeConstraints` that the caller gives. It adds no function for the outward height.
  - c0113: `checks.placement` with `rules_of(model)`, `judge(design, rules, *, pads) -> RuleReport(issues, counts)`, the stage `placement.rules` in both check pipelines, `result.rules` of `place`, `result.placement.rules` of `build`, and the codes `placement.rule-unresolved` and `placement.rule-skipped`. Its Decision 5 gives the face rule of a keep-out (`H-K-PLACE-KEEPOUT`): an area on `F.Cu` concerns top-side parts, one on `B.Cu` bottom-side parts, one on inner layers none.
  - c0103: `design.rule_area(name, outline, *, layers, forbid)` and `Keepout.name`.
  - c0096 (`codex/c0096-constrained-placement`): `MechanicalVolume` and `MechanicalConstraints`, data of one placement request.

**Nothing was measured for this change.** It defines a rule of Fenolite's own on values the user gives. The face rule it borrows was measured for c0113 (its measurement 1, 18 cases on 9.0.9 and 10.0.6).

**Constraints.** Stdlib only; integer nanometres; no float. Fenolite ships no height and no limit. `model` imports nothing above `core`; the DSL imports only `core` and `model`; `checks` only `model`, `geometry` and `backends.base`; `lens` imports neither `dsl` nor `checks`.

## Goals / Non-Goals

**Goals**
- A part's height has one home and one function that reads it.
- A script can state a height and a limit; `check` gates the limit; `place` and `build` report it.
- A board imported from Altium, whose bodies carry real heights, is judged by the same function.

**Non-Goals**
- Everything under "Non-goals" in the proposal.
- A new analysis of volumes: c0099 has it.

## Decisions

1. **One source of height: `ComponentBody`, read by one function.** `fenolite.model.board.outward_height(footprint) -> Nm | None` returns the largest upper bound of the footprint's known bodies: for a body with signed bounds its `z_max`, otherwise its `height`; a body with `projection_unknown` is skipped; the result is `None` when no known body remains or the largest bound is not positive. That is c0099's sentence, as code, in the module that owns the entity. Every consumer of this change calls it, and the requirement says that no other code of the package may compute a part's height from other data.
   - Rejected: `Component.height` in the circuit layer, the first proposal. A component would then have a height and its footprint bodies with heights; two values, no rule which wins, and an imported board fills only one of them.
   - Rejected: the function in `checks.placement`. c0096's body checker, a later exporter or the placer of v0.5a would need it too, and `placement` may not import `checks`.
   - Rejected: a property `FootprintInstance.height`. The dataclass is a record of what a file or a script says; a derived value on it would look like stored data and would enter no schema.

2. **A script states a height by giving the part a body.** `Part(…, height=h)`, keyword-only, a positive length. `dsl.heights(design)` returns the heights by component path, plain data as `dsl.placements(design)` is; the build gives each placed footprint one `ComponentBody(id=derived_id("bdy", "dsl", "height:<path>"), kind="extruded", height=h, standoff=0, outline=(), name="height")`, appended after the bodies its definition brings.
   - No signed bounds are set: the legacy `height` of a body without them is its upper bound (c0099), and a script that says "9 mm tall" states nothing about the underside.
   - No outline: the script states a number. c0121's rule holds here too: no body shape is derived from a courtyard, a fabrication outline or a pad box.
   - `Part.height` holds the value in the script; it is the input of the body and nothing else reads it.
   - Rejected: `part.body(height=…, outline=…)` now. Which outline, on which side of a flipped part, and catalog heights with sources are the questions c0121 left open; a limit over an area needs none of them.
   - Rejected: the body on the library definition (`FootprintDef.bodies`). Two parts of one footprint differ in height (two electrolytic capacitors in one land pattern).

3. **The KiCad build keeps the body in `.fenolite/board.json`, through rebuilds.** `build_design(…, heights=None)` attaches the bodies to the built footprints. The merge with an existing board copies the built footprint's `bodies` onto the node it keeps, because a KiCad file holds no body and the script is their only source. No KiCad file changes.
   - Rejected: writing a footprint property (`fenolite.height`). It would change "User properties on built footprints" for a value KiCad ignores, and it would be a second home.

4. **Height limits name rule areas.** `design.height_limit(area, *, max, severity="error")` records `HeightLimit(area, max, severity)` in `RuleSet.heights`, value objects in area order, one limit per name. The name is not checked at the call: an area drawn in KiCad is known only on the board. Every rule area named `area` on the board limits the parts under it.
   - Rejected: a field on the rule area (`rule_area(max_height=…)`). KiCad's file has no place for it, so the board read back would lose it.
   - Rejected: an outline in the limit itself, a second way to draw an area that KiCad would not show.

5. **Under an area: c0113's face rule, on the part's own face.** A footprint is under an area when the area's layers hold `F.Cu` and the footprint is on the top side, or `B.Cu` and the bottom side, and the interior of a ring of its own face (`PlacedExtent.own`) meets the interior of the area's outline (`interiors_intersect`). An area on inner layers only judges no part. A part without a courtyard is judged on its pad hull, and its finding says "(approximate extent)". The body's own outline is not used even when it has one: a body from a script has none, and one rule for every part is easier to predict than two.

6. **Findings.** `placement.too-tall` with the limit's severity when the height is above `max`; `placement.height-unknown` (warning) for a judged part without a known height: an unknown height under a limit is never a pass. A limit whose area the board does not hold gives c0113's `placement.rule-unresolved` (error). A footprint with the attribute `dnp` is not judged. One with `board_only`, or whose pads are all non-plated holes, is judged only when its height is known: a logo drawn in KiCad has no part in the script, and a mounting hole has no body of its own.

7. **A limit is one number over one area; it is not c0099's volume check.** `judge_heights` compares `outward_height` with `max`. It does not call `check_body_volumes`.
   - Why not lower a limit to a `VolumeConstraints` obstacle (the area, from `max` upwards): that check needs each body's outline and the board thickness for the bottom face, and answers "unknown" without them; a body from a script has no outline. The simple rule answers for every part that has a height.
   - What c0099 still owns, and this change does not approximate: a body that reaches below its mounting face, a tall part on the other side, a shape in space, permitted penetrations. `docs/placement.md` points there.

8. **Beside c0096.** `MechanicalVolume` and `MechanicalConstraints` are inputs of one `place --strategy constrained` request; `HeightLimit` is a rule of the design, stored and judged on every `check`. Neither is converted into the other: c0096's design asks that they not be "silently substituted". If c0096's body checker needs a part's height, it calls `outward_height`.

9. **The second backend.**
   - *Rule table.* A height limit is a value object beside `RuleSet.rules`, as c0113's proximity rules are. It has no `RuleKind`, so `rulemap.TABLE` (c0084: one row per kind) gains no row and no test of the table sees a new kind. Altium's own rule kind `Height` is seen once in the corpus and not mapped (`docs/formats/altium/rule-file.md`); writing it is a later row of that table, with facts first.
   - *Build.* `build --target altium` stores `RuleSet.heights` in `.fenolite/rules.json`. It judges no placement rule (the living "Placement legality in a build" has no guard for that target) and says so with c0113's `altium.not-lowered` info of kind `placement-rule`, whose count then includes the height limits.
   - *Bodies.* A body from `Part(height=…)` has no outline, so c0121's writer does not write it: with `--altium-bodies extruded` it is counted under the kind `body` of `altium.not-lowered`, as c0121 already does for such a body; without the option no body is written at all. By c0121's rule the stored board of an Altium build holds the bodies that were written, so this body is not in it, and this change does not alter that rule (its round-trip check compares stored bodies with the document).
   - *Check.* The stage runs on Altium documents (c0113). A part's height is `outward_height` of its footprint in the PCB reading, which holds the bodies of the document. So a limit is judged for every part whose document holds a body, a board first imported from Altium for instance, and a part without one gives `placement.height-unknown`. For a script built only for Altium that is every part with a script height: a stated limit of this change, written in `docs/altium.md`, and removed when a script body can carry an outline (Open Questions).
   - Rejected: keeping the script's bodies in the stored board of an Altium build although they are not in the document. The round-trip stage of c0121 would report each as a body that the document lost.

10. **Where heights are read for a judge.** One carrier per input, one function:
    - the board being judged, when its footprint holds a body (an Altium reading);
    - else the footprint of the same component path in the `.fenolite/` model of a built project (a KiCad project, whose file holds no body);
    - else unknown.
    `checks.placement.heights_of(design, model) -> Mapping[str, Nm | None]` does this by footprint id and calls `outward_height` on the footprint it picked; it never mixes the bodies of the two.

11. **Reports extend c0113's, by ADDED requirements.** c0113's stage, its `place` reply and its build guard are named and extended "in addition"; none of c0113's requirements is modified, because they are not living on `dev` when this proposal is written and a MODIFIED delta must be made from a living text. `RuleReport.counts` is a mapping by rule family in c0113 for this reason; this change adds `{"height": {"judged", "failed", "unknown"}}`.
    - If c0113's requirements are living when this change is implemented, task 0.1 checks whether an ADDED requirement here contradicts a sentence there; the two were written together and none does at `9aba2dff` plus the proposal of c0113 of 2026-10-07.

12. **Explain entries and the model key.** Task 4.1 adds the tables of the two codes to `src/fenolite/cli/data/explain.toml`. Task 2.2 writes into `docs/design-model.md` that `heights` is omitted when empty and that 0.2.x and 0.3.0 cannot read a `rules.json` that carries it.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/board.py` | `outward_height(footprint: FootprintInstance) -> Nm \| None` |
| `src/fenolite/model/rules.py` | value object `HeightLimit(area, max, severity="error")`; `RuleSet.heights` |
| `schemas/fenolite.model.v0/rules.json` | regenerated |
| `src/fenolite/dsl/part.py`, `design.py`, `convert.py`, `__init__.py` | `Part(…, height=None)`, `Part.height`; `Design.height_limit(area, *, max, severity="error")`; `heights(design) -> Mapping[str, Nm]`, re-exported; `RuleSet.heights` in `to_model` |
| `src/fenolite/lens/build.py`, `lens/preserve.py` | `build_design(…, heights=None)`: the body on the built footprint; the merge keeps the built footprint's `bodies` |
| `src/fenolite/checks/placement.py` (c0113) | `heights_of(design, model)`; `judge_heights(design, limits, heights, *, extents) -> RuleReport`; `rules_of` also gives `heights`; the stage calls it |
| `src/fenolite/checks/codes.py` | `placement.too-tall`, `placement.height-unknown` |
| `src/fenolite/cli/cmd_place.py`, `cli/cmd_build.py` | the height report of `place` and of the placement guard; `heights` handed to `build_design` |
| `src/fenolite/cli/data/explain.toml` | one table for each of the two codes |
| `tests/unit/model/test_outward_height.py`, `test_rules.py`; `tests/unit/dsl/test_part_height.py`; `tests/unit/lens/test_build_bodies.py`; `tests/unit/checks/test_height_limits.py`, `test_placement_stage.py`; `tests/unit/cli/test_place_cmd.py`, `test_build_placement_guard.py`, `test_check_altium.py` | unit tests; every layout is written by its test |
| `docs/placement.md`, `docs/dsl.md`, `docs/design-model.md`, `docs/cli-contract.md`, `docs/altium.md` | the one source of height, the DSL calls, the limit and its face rule, the codes, the model key and its compatibility sentence, the limit on the Altium target |

No file under `tests/data/` is added, and no source is registered.

## Sources registered by this change

None. The names it reads are the project's own (`ComponentBody`, c0099's fields, c0113's reports). The Altium rule kind `Height` is cited from the existing row of `docs/formats/altium/rule-file.md` (S-0297) and is not used.

## Hypotheses registered by this change

None. The height of a part and the limit are definitions, proved by unit scenarios. The face rule rests on `H-K-PLACE-KEEPOUT` (c0113), used without changing its level.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| `outward_height` | mechanical: c0099's definition as code | `tests/unit/model/test_outward_height.py` |
| a script height becomes a body, kept through a rebuild | mechanical | `tests/unit/dsl/test_part_height.py`, `tests/unit/lens/test_build_bodies.py` |
| height limits judged | `INFERRED`: Fenolite's own rule; the face of an area rests on `H-K-PLACE-KEEPOUT` | `tests/unit/checks/test_height_limits.py` on authored layouts |
| the stage, `place`, the build guard | mechanical | their unit tests |
| heights of an Altium reading | the import's level (the row c0099 registers for the bounds of an imported body, and the rows of c0043) | `tests/unit/cli/test_check_altium.py -k height` |

## Risks / Trade-offs

- **Wrong heights.** A height is what the user wrote. Mitigation: nothing is assumed; an unknown height under a limit is a warning, never a pass.
- **The Altium target judges little.** A script height is not in an Altium document (Decision 9). Mitigation: `placement.height-unknown` names every such part, so the gap shows in every reply; `docs/altium.md` says why.
- **A body without an outline is a thin thing.** c0099's volume check answers "unknown" for it. That is correct: the script gave a number, not a shape.
- **Bodies on a rebuild.** The merge is changed to keep built bodies. A board whose stored model already holds bodies for a KiCad build does not exist today, so no stored file changes meaning; the test of task 3.2 pins the new rule.
- **Three changes before this one.** c0099, c0113 and c0103 must be on `dev`. If c0113 slips, nothing of this change can be built; the model function and the DSL input (tasks 1 to 3) can, and are ordered first.

## Migration Plan

- Additive. A script without `height=` and without `height_limit` gives equal models and equal bytes: `heights` is left out of `rules.json` when empty, and a footprint without bodies writes no `bodies` key.
- The other direction does not hold: 0.2.x and 0.3.0 cannot read a `rules.json` that carries `heights`. The board layer gains no key: a footprint with a script height uses `bodies` and the fields of the living "Component bodies".
- `check` can exit 5 for a limit of severity `error` on a project that states one.
- Rollback: remove the DSL arguments and the judge; `RuleSet.heights` can stay empty, and `outward_height` has no side effect.

## Budget (2 days)

| part | days |
|---|---|
| entry check; `outward_height` and its scenarios | 0.25 |
| model: `HeightLimit`, `RuleSet.heights`, schema, the compatibility sentence | 0.25 |
| DSL: `Part(height=…)`, `heights`, `height_limit`; the body in the build and through the merge | 0.5 |
| `heights_of`, `judge_heights`, the two codes, explain entries | 0.5 |
| the stage, `place`, the build guard, the Altium reading | 0.25 |
| documentation and closing | 0.25 |

Cut order: (1) the report in `place` (−0.1; `check` and `build` still report). Never cut: `outward_height` as the one reader, the body from the script, the limit judged by `check`.

## Open Questions

- **An outline for a script body.** With one, c0121 could write the body into an Altium document and the Altium target could judge a limit; c0099 could judge it in space. Default: not here; it is the DSL decision c0121 names ("which outline, which side of a flipped part, catalog data with sources").
- **Should the stored board of an Altium build keep script bodies that were not written?** Default: no (Decision 9); it would need c0121's round-trip stage to tell "not written by rule" from "lost".
- **Altium's rule kind `Height`.** Default: not written; a later row of the Altium rule table, after its keys are recorded as facts.
- **A lower bound** (a part that must clear a minimum height, or a standoff rule). Default: no; nobody asked.
- **Should `placement.height-unknown` be an error?** Default: warning, so that a board with one undeclared part is not blocked; a limit of severity `error` still fails for every part that is too tall.
