## Why

A board that goes into an enclosure has places where a part may not be tall: under a lid, a heat sink, a display, a neighbouring board. The review of 2026-10-05 of the gaps to a complex board (milestone v0.4; `docs/roadmap.md`, "The complex board, c0100–c0120") found that no part of a script has a height and that nothing checks one. Both are still true at `origin/dev` `9aba2dff`: no call of `ComponentBody` is under `src/fenolite/dsl`, and no check reads a body's height.

c0113 first held this as `Part(height=…)`, `Component.height` and `design.height_limit(…)`. The review of the proposals on 2026-10-07 found that a part's height would then live in three places: `Component.height` (c0113), `ComponentBody.height` with the signed bounds that c0099 adds (`z_min`, `z_max`, `projection_unknown`), and a `part.body(height=…)` that c0121 left for a later decision. The maintainer decided the same day (decision 3): height rules leave c0113 and become a change of their own, written after c0099 is on `dev`, with **one source of height**. This is that change.

## What Changes

- **One source of height: the body.** A part's height is the outward height of the `ComponentBody` entities of its footprint, as c0099's "Component bodies" defines it: the largest upper bound of its known bodies, `z_max` when a body has signed bounds, its `height` otherwise; a body with `projection_unknown` makes no claim. `fenolite.model.board.outward_height(footprint)` is the one function that computes it, and every judge calls it. No `Component.height`, no property on the footprint, no second table.
- **A script states a height as a body.** `Part(…, height=h)` gives the part's placed footprint one extruded `ComponentBody` of height `h`, standoff 0 and no outline. The KiCad build keeps it in `.fenolite/board.json` only, as "Component bodies" already says of every body, and carries it through a rebuild.
- **Height limits.** `design.height_limit(area, *, max, severity="error")`: every rule area named `area` (c0103) limits the parts under it to `max`. Stored as `RuleSet.heights`.
- **Judged where c0113 judges placement rules.** The stage `placement.rules` of `check`, `place` and the placement guard of `build` report `placement.too-tall` and `placement.height-unknown`; the counts gain the family `height`.
- Two issue codes, each with its entry in `cli/data/explain.toml`.

**Limits.** A height is what the script or the imported document says; Fenolite reads no 3D model geometry. A body from `Part(height=…)` has no outline, so the area test uses the part's courtyard, and the Altium body writer of c0121 does not write it (it reports it). On the Altium target a height limit is therefore judged only for parts whose document holds a body; the others are `placement.height-unknown`. A part with `dnp` is not judged. The grid of `place` does not know heights. The check is one number against one area on one face: bodies that cross the board, obstacles in space and penetrations are c0099's analysis.

Size: 2 design-days.

## Prerequisites

Read at `origin/dev` `9aba2dff` on 2026-10-07. This proposal is text only; it is implemented after all of the following are on `dev`.

- `0.3.0` released, which archives c0121 (component bodies written for Altium, with its rule for the stored board of an Altium build) and c0126.
- **c0099** (signed body bounds and body volumes; implemented on `codex/c0099-body-volumes`): `outward_height` reads its fields and implements its sentence on the outward height of a part. Without c0099 this change is not started.
- **c0113** (proximity rules, the stage `placement.rules`, `RuleReport`, `rules_of`): this change extends its stage and its three reports by ADDED requirements that name them.
- **c0103** (rule areas, `Keepout.name`): a height limit names an area.
- c0096 (constrained placement): its `MechanicalVolume` and `MechanicalConstraints` are request data of one `place` run; nothing here reads or replaces them (design, Decision 8).
- c0129 (the identity of a body read from Altium, planned after c0099): no dependency.
- Waiting for this change: c0119, if the yardstick board states an enclosure limit.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Outward height of a part", "Height limits in the model".
- `design-dsl`: ADDED "Part heights and height limits in the DSL", "Part heights in a build".
- `placement`: ADDED "Height limits judged".
- `verification-loop`: ADDED "Height limits in the placement stage", "Height limit issue codes".
- `cli-contract`: ADDED "Height limits in place".

## Non-goals

- A height on the component (`Component.height`), on the footprint as a property, or in a table per library footprint: nowhere. One source (design, Decision 1).
- An outline for a body stated in a script, and catalog heights with sources: a later change of the DSL, as c0121 says; this change does not derive an outline from a courtyard.
- Heights from 3D model files: nowhere, because Fenolite reads no model geometry.
- Volumes in space, parts that reach through the board, clearances to an enclosure wall: c0099's `check_body_volumes` with constraints the caller gives. A height limit is not lowered to it (design, Decision 7).
- The grid of `place` avoiding areas that are too low for a part: nowhere now; the annealing placer of v0.5a takes height limits as hard constraints.
- A height rule written into rule files: nowhere in this change. KiCad's rule language has no height. Altium rule files hold a kind `Height` (`docs/formats/altium/rule-file.md`, "Rule kinds seen": one record of one public export, S-0297, not mapped); writing it needs its keys and its scope recorded as format facts first, and a row in the Altium rule table, a change of that table of its own. Until then a height limit is no `RuleKind`, the table of c0084 gains no row, and the Altium build says that it wrote none (design, Decision 9).
- Refusing `place` or `build` for a height finding: nowhere; `check` is the gate, as for every placement rule.

## Evidence level required

- The height rule and the limit are Fenolite's own definitions: `INFERRED`, proved by unit tests on authored layouts. No oracle judges them.
- The face rule of "a part under an area" is the one of `H-K-PLACE-KEEPOUT` (c0113); this change adds no hypothesis and no source.

## Impact

- Changed: `model/board.py` (one function), `model/rules.py`, `dsl/part.py`, `dsl/design.py`, `dsl/convert.py`, `lens/build.py`, `lens/preserve.py`, `checks/placement.py`, `checks/codes.py`, `cli/cmd_place.py`, `cli/cmd_build.py`, `cli/data/explain.toml`, one schema, docs.
- New model key `heights` in `rules.json`, omitted when empty; `.fenolite/board.json` of a design that states a height gains `bodies` on those footprints. A design that states neither keeps every byte. 0.2.x and 0.3.0 cannot read a `rules.json` that carries `heights`.
- `check` can exit 5 for a part above a limit of severity `error`.
- No KiCad file changes: KiCad stores no body and no height rule.
